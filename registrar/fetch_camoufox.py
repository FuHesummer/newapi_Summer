"""下载 Camoufox 浏览器二进制文件（支持 GitHub 代理加速）"""
import camoufox.pkgman as pm
from camoufox.__main__ import CamoufoxUpdate

# 保存原始下载函数
original_webdl = pm.webdl

def patched_webdl(url, **kwargs):
    """通过代理下载 GitHub Release 文件"""
    if 'github.com' in url:
        # 尝试代理 1: ghgo.xyz
        proxy_url = url.replace('https://github.com', 'https://ghgo.xyz/https://github.com')
        print(f'Using proxy: {proxy_url}')
        try:
            return original_webdl(proxy_url, **kwargs)
        except Exception as e:
            print(f'Proxy 1 failed ({e}), trying ghfast.top...')
        # 尝试代理 2: ghfast.top
        proxy_url2 = url.replace('https://github.com', 'https://ghfast.top/https://github.com')
        try:
            return original_webdl(proxy_url2, **kwargs)
        except Exception as e:
            print(f'Proxy 2 failed ({e}), trying direct...')
        # 兜底: 直连
        return original_webdl(url, **kwargs)
    return original_webdl(url, **kwargs)

pm.webdl = patched_webdl
CamoufoxUpdate().update()
print('Camoufox fetch complete!')
