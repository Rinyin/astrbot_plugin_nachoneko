from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import astrbot.api.message_components as Comp
import os
import logging
import requests
from datetime import datetime

class ImageDownloader:
    _log_configured = False  # 类级日志配置标记

    def __init__(self, save_folder='downloaded_images', log_folder='logs'):
        """
        初始化下载器
        :param save_folder: 图片存储目录（默认：downloaded_images）
        :param log_folder: 日志存储目录（默认：logs）
        """
        self.save_folder = save_folder
        self.log_folder = log_folder
        
        # 创建必要目录
        os.makedirs(self.save_folder, exist_ok=True)
        self._configure_logger()

    def _configure_logger(self):
        """配置日志记录系统"""
        if not ImageDownloader._log_configured:
            self.logger = logging.getLogger('ImageDownloader')
            self.logger.setLevel(logging.INFO)

            # 创建日志目录
            os.makedirs(self.log_folder, exist_ok=True)
            
            # 配置文件handler
            log_file = os.path.join(
                self.log_folder,
                f'downloader_{datetime.now().strftime("%Y%m%d")}.log'
            )
            file_handler = logging.FileHandler(log_file)
            
            # 配置日志格式
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(formatter)
            
            self.logger.addHandler(file_handler)
            ImageDownloader._log_configured = True

    def fetch_image(self):
        """
        执行完整的图片获取流程
        :return: 成功返回图片路径，失败返回None
        """
        api_url = 'https://xiaobapi.top/api/xb/api/gcmm.php'
        params = {'type': 1}

        try:
            # 发送网络请求
            response = requests.get(api_url, params=params, timeout=15)
            response.raise_for_status()

            # 验证内容类型
            content_type = response.headers.get('Content-Type', '')
            if 'image' not in content_type:
                self.logger.error(
                    f"无效内容类型：{content_type} | URL：{response.url}"
                )
                return None

            # 生成带时间戳的唯一文件名
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
            ext = self._parse_extension(content_type)
            save_path = os.path.join(self.save_folder, f'image_{timestamp}.{ext}')

            # 保存图片文件
            with open(save_path, 'wb') as f:
                f.write(response.content)

            self.logger.info(f"图片保存成功：{save_path}")
            return save_path

        except requests.exceptions.RequestException as e:
            self.logger.error(
                f"网络请求异常：{str(e)}",
                exc_info=True
            )
        except IOError as e:
            self.logger.error(
                f"文件操作异常：{str(e)}",
                exc_info=True
            )
        except Exception as e:
            self.logger.error(
                f"未处理的异常：{str(e)}",
                exc_info=True
            )
        return None

    def _parse_extension(self, content_type):
        """解析内容类型获取扩展名"""
        type_map = {
            'image/jpeg': 'jpg',
            'image/png': 'png',
            'image/gif': 'gif'
        }
        return type_map.get(content_type.split(';')[0].strip(), 'jpg')
        
    def get_all_images(self):
        """获取所有图片文件列表"""
        try:
            if not os.path.exists(self.save_folder):
                return []
                
            # 获取图片文件夹中的所有文件
            files = os.listdir(self.save_folder)
            # 过滤出图片文件（简单判断扩展名）
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
        """清理所有图片文件"""
        success_count = 0
        failed_count = 0
        
        for image_path in self.get_all_images():
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
        # 创建下载器实例作为类属性，可以重复使用
        self.downloader = ImageDownloader()

    @filter.command("neko")
    async def neko(self, event: AstrMessageEvent):
        yield event.plain_result("喵喵喵~")
        return await self._send_neko_image(event)
    
    async def _send_neko_image(self, event: AstrMessageEvent):
        """处理猫猫图片的获取、发送和清理"""
        try:
            # 使用类属性中的下载器实例
            image_path = self.downloader.fetch_image()
            
            if not image_path:
                return event.plain_result("获取图片失败，请稍后再试。")
            
            # 检查文件是否存在
            if not os.path.exists(image_path):
                return event.plain_result("图片文件丢失，请稍后再试。")
                
            # 发送图片
            try:
                result = event.chain_result(Comp.Image.fromFileSystem(image_path))
                yield result
                logger.info(f"成功发送图片: {image_path}")
            except Exception as e:
                logger.error(f"发送图片失败: {str(e)}")
                return event.plain_result(f"发送图片失败: {str(e)}")
            
            # 删除图片文件
            try:
                os.remove(image_path)
                logger.info(f"成功删除图片: {image_path}")
            except Exception as e:
                logger.error(f"删除图片失败: {str(e)}")
                return event.plain_result("图片已发送，但清理失败。")
                
        except Exception as e:
            logger.error(f"处理图片请求时发生错误: {str(e)}")
            return event.plain_result(f"处理请求时发生错误: {str(e)}")
            
    async def terminate(self):
        """插件卸载时清理资源"""
        try:
            # 清理所有剩余图片
            success_count, failed_count = self.downloader.cleanup_images()
            logger.info(f"插件卸载时清理图片：成功 {success_count} 个，失败 {failed_count} 个")
        except Exception as e:
            logger.error(f"插件卸载时清理资源失败: {str(e)}")
