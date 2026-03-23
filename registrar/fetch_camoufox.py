"""下载 Camoufox 浏览器二进制文件（支持 GitHub 代理加速）

camoufox 内部: install() -> self.download_file(temp_file, self.url)
download_file(self, temp_file, url) -> webdl(url, buffer=file)
"""
import camoufox.pkgman as pm

_original_download_file = pm.CamoufoxFetcher.download_file

def _patched_download_file(self, temp_file, url):
    """拦截 download_file，替换 GitHub URL 为代理地址"""
    if url and 'github.com' in url:
        proxies = [
            ('ghgo.xyz', url.replace('https://github.com', 'https://ghgo.xyz/https://github.com')),
            ('ghfast.top', url.replace('https://github.com', 'https://ghfast.top/https://github.com')),
        ]
        for name, proxy_url in proxies:
            print(f'[camoufox] Trying {name}: {proxy_url}', flush=True)
            try:
                return _original_download_file(self, temp_file, proxy_url)
            except Exception as e:
                print(f'[camoufox] {name} failed: {e}', flush=True)
        print(f'[camoufox] All proxies failed, using direct: {url}', flush=True)
    return _original_download_file(self, temp_file, url)

pm.CamoufoxFetcher.download_file = _patched_download_file

from camoufox.__main__ import CamoufoxUpdate
CamoufoxUpdate().update()
print('[camoufox] Done!', flush=True)
