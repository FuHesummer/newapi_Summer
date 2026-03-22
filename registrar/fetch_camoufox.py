"""下载 Camoufox 浏览器二进制文件（支持 GitHub 代理加速）"""
import camoufox.pkgman as pm
from camoufox.__main__ import CamoufoxUpdate

# Patch 1: 替换 webdl 下载函数
original_webdl = pm.webdl

def patched_webdl(url, **kwargs):
    """通过代理下载 GitHub Release 文件"""
    if 'github.com' in url:
        proxies = [
            ('ghgo.xyz', url.replace('https://github.com', 'https://ghgo.xyz/https://github.com')),
            ('ghfast.top', url.replace('https://github.com', 'https://ghfast.top/https://github.com')),
        ]
        for name, proxy_url in proxies:
            print(f'[fetch_camoufox] Trying {name}: {proxy_url}', flush=True)
            try:
                return original_webdl(proxy_url, **kwargs)
            except Exception as e:
                print(f'[fetch_camoufox] {name} failed: {e}', flush=True)
        print(f'[fetch_camoufox] All proxies failed, trying direct: {url}', flush=True)
    return original_webdl(url, **kwargs)

pm.webdl = patched_webdl

# Patch 2: 替换 download_file 方法，拦截 URL 在更上层
original_download_file = pm.CamoufoxFetcher.download_file

def patched_download_file(self, temp_file, url):
    """在 download_file 层面替换 GitHub URL"""
    if 'github.com' in url:
        proxy_url = url.replace('https://github.com', 'https://ghgo.xyz/https://github.com')
        print(f'[fetch_camoufox] Intercepted download_file, using proxy: {proxy_url}', flush=True)
        try:
            return original_download_file(self, temp_file, proxy_url)
        except Exception as e:
            print(f'[fetch_camoufox] Proxy failed ({e}), trying ghfast.top...', flush=True)
            proxy_url2 = url.replace('https://github.com', 'https://ghfast.top/https://github.com')
            try:
                return original_download_file(self, temp_file, proxy_url2)
            except Exception as e2:
                print(f'[fetch_camoufox] All proxies failed, direct download: {url}', flush=True)
                return original_download_file(self, temp_file, url)
    return original_download_file(self, temp_file, url)

pm.CamoufoxFetcher.download_file = patched_download_file

# 执行下载
CamoufoxUpdate().update()
print('[fetch_camoufox] Done!', flush=True)
