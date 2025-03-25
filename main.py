from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import astrbot.api.message_components as Comp
import os
import logging
import requests
from datetime import datetime
import urllib3

# 禁用SSL证书警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class ImageDownloader:
    _log_configured = False

    def __init__(self, save_folder='downloaded_images', log_folder='logs'):
        self.save_folder = save_folder
        self.log_folder = log_folder
        os.makedirs(self.save_folder, exist_ok=True)
        self._configure_logger()

    def _configure_logger(self):
        if not ImageDownloader._log_configured:
            self.logger = logging.getLogger('ImageDownloader')
            self.logger.setLevel(logging.INFO)
            os.makedirs(self.log_folder, exist_ok=True)
            log_file = os.path.join(
                self.log_folder,
                f'downloader_{datetime.now().strftime("%Y%m%d")}.log'
            )
            file_handler = logging.FileHandler(log_file)
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
            ImageDownloader._log_configured = True

    def fetch_image(self):
        api_url = 'https://xiaobapi.top/api/xb/api/gcmm.php'
        params = {'type': 1}
        try:
            # 添加 verify=False 绕过SSL验证
            response = requests.get(api_url, params=params, timeout=15, verify=False)
            response.raise_for_status()

            content_type = response.headers.get('Content-Type', '')
            if 'image' not in content_type:
                self.logger.error(f"无效内容类型：{content_type} | URL：{response.url}")
                return None

            timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
            ext = self._parse_extension(content_type)
            save_path = os.path.join(self.save_folder, f'image_{timestamp}.{ext}')

            with open(save_path, 'wb') as f:
                f.write(response.content)

            self.logger.info(f"图片保存成功：{save_path}")
            return save_path

        except requests.exceptions.RequestException as e:
            self.logger.error(f"网络请求异常：{str(e)}", exc_info=True)
        except IOError as e:
            self.logger.error(f"文件操作异常：{str(e)}", exc_info=True)
        except Exception as e:
            self.logger.error(f"未处理的异常：{str(e)}", exc_info=True)
        return None

    def _parse_extension(self, content_type):
        type_map = {
            'image/jpeg': 'jpg',
            'image/png': 'png',
            'image/gif': 'gif'
        }
        return type_map.get(content_type.split(';')[0].strip(), 'jpg')
        
    def get_all_images(self):
        try:
            if not os.path.exists(self.save_folder):
                return []
                
            files = os.listdir(self.save_folder)
            image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
            image_files = [
                os.path.join(self.save_folder, f) 
                for f in files 
                if os.path.splitext(f)[1].lower() in image_extensions
            ]
            return image_files
        except Exception as e:
            self.logger.error(f"获取图片列表失败: {str(e)}")
            return []
            
    def cleanup_images(self):
        success_count = 0
        failed_count = 0
        
        for image_path in self.get_all_images():
            # 添加路径类型校验
            if not isinstance(image_path, (str, bytes, os.PathLike)):
                self.logger.error(f"无效路径类型: {type(image_path)}")
                failed_count += 1
                continue
            try:
                os.remove(image_path)
                self.logger.info(f"清理图片成功: {image_path}")
                success_count += 1
            except Exception as e:
                self.logger.error(f"清理图片失败: {image_path}, 错误: {str(e)}")
                failed_count += 1
                
        return success_count, failed_count

@register("nachoneko", "Rinyin", "随机甘城猫猫图片", "1.0.0")
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.downloader = ImageDownloader()

    @filter.command("neko")
    async def neko(self, event: AstrMessageEvent):
        yield event.plain_result("喵喵喵~")
        async for result in self._send_neko_image(event):  # 确保方法调用正确
            yield result
    
    # 确保方法正确定义在类内部，且为异步方法
async def _send_neko_image(self, event: AstrMessageEvent):
    try:
        image_path = self.downloader.fetch_image()
        
        if not image_path:
            yield event.plain_result("获取图片失败，请稍后再试。")
            return
        
        # 严格校验文件存在性
        if not os.path.exists(image_path):
            logger.error(f"图片文件不存在: {image_path}")
            yield event.plain_result("图片文件丢失，请稍后再试。")
            return
            
        # 发送图片（将 Image 对象包装在列表中）
        try:
            result = event.chain_result([Comp.Image.fromFileSystem(image_path)])
            yield result
            logger.info(f"成功发送图片: {image_path}")
        except Exception as e:
            logger.error(f"发送图片失败: {str(e)}")
            yield event.plain_result(f"发送图片失败: {str(e)}")
            return
        
        # 删除图片文件
        try:
            os.remove(image_path)
            logger.info(f"成功删除图片: {image_path}")
        except Exception as e:
            logger.error(f"删除图片失败: {str(e)}")
            yield event.plain_result("图片已发送，但清理失败。")
            
    except Exception as e:  # 添加外层 try 对应的 except
        logger.error(f"处理图片请求时发生错误: {str(e)}")
        yield event.plain_result(f"处理请求时发生错误: {str(e)}")
            
    async def terminate(self):
        try:
            # 修复返回值解包方式
            success_count, failed_count = self.downloader.cleanup_images()
            logger.info(f"插件卸载时清理图片：成功 {success_count} 个，失败 {failed_count} 个")
        except Exception as e:
            logger.error(f"插件卸载时清理资源失败: {str(e)}")