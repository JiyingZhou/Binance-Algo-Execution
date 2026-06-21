import os
import warnings
from urllib3.exceptions import InsecureRequestWarning
from binance import Client
from binance.exceptions import BinanceAPIException
from dotenv import load_dotenv

# 加载项目根目录下的.env文件（路径根据实际情况调整）
load_dotenv()  # 默认读取当前工作目录的.env文件


# 忽略不安全请求警告
warnings.filterwarnings("ignore", category=InsecureRequestWarning)

# 代理配置（全局变量，可被导入使用）
proxies = {
    'http': 'http://127.0.0.1:7890',
    'https': 'http://127.0.0.1:7897'
}

# 全局客户端实例（单例）
_global_client = None


def get_binance_client():
    """
    单例模式初始化并返回Binance客户端（全局复用，避免重复登录）
    :return: 已验证连接的Binance Client对象
    """
    global _global_client

    # 如果客户端已初始化，直接返回复用
    if _global_client is not None:
        return _global_client

    # 读取密钥（此时读取的是.env文件中的值，而非系统全局变量）
    api_key = os.getenv('BINANCE_API_KEY')
    api_secret = os.getenv('BINANCE_API_SECRET')

    # 验证密钥是否存在（避免后续报错）
    if not api_key or not api_secret:
        raise ValueError("请先设置 BINANCE_API_KEY 和 BINANCE_API_SECRET 环境变量")
    if len(api_key) < 50 or len(api_secret) < 50:
        raise ValueError("API密钥长度异常，请检查是否复制正确")

    try:
        # 2. 初始化客户端（带代理和SSL配置）
        client = Client(
            api_key,
            api_secret,
            requests_params={'proxies': proxies, 'verify': False}
        )
        # 3. 主动Ping测试连接
        client.ping()
        print("✅ Binance客户端初始化成功（连接已验证）")

        # 赋值给全局变量，下次直接复用
        _global_client = client
        return client

    except BinanceAPIException as e:
        raise Exception(f"API密钥/权限错误: {e}") from e
    except Exception as e:
        raise Exception(f"客户端初始化失败: {e}") from e


# 保留独立运行的能力
if __name__ == "__main__":
    get_binance_client()
