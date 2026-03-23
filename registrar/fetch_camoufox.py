"""下载 Camoufox 浏览器二进制文件（支持 GitHub 代理加速）

camoufox 内部调用链:
  CamoufoxUpdate().update() -> self.install()
  install() -> self.download_file(temp_file)
  download_file(temp_file) -> webdl(self.url, buffer=file)

self.url 是只读 property，所以直接 patch download_file，
在里面替换 self.url 为代理 URL 再调用 webdl。
"""
import camoufox.pkgman as pm

_original_download_file = pm.CamoufoxFetcher.download_file

def _patched_download_file(self, temp_file):
    """拦截 download_file，替换 URL 为代理地址"""
    url = self.url
    if url and 'github.com' in url:
        proxies = [
            ('ghgo.xyz', url.replace('https://github.com', 'https://ghgo.xyz/https://github.com')),
            ('ghfast.top', url.replace('https://github.com', 'https://ghfast.top/https://github.com')),
        ]
        for name, proxy_url in proxies:
            print(f'[camoufox] Trying {name}: {proxy_url}', flush=True)
            try:
                return pm.webdl(proxy_url, buffer=open(temp_file, 'wb'))
            except Exception as e:
                print(f'[camoufox] {name} failed: {e}', flush=True)
        print(f'[camoufox] All proxies failed, using direct: {url}', flush=True)
    # 兜底调用原始方法
    return _original_download_file(self, temp_file)

pm.CamoufoxFetcher.download_file = _patched_download_file

from camoufox.__main__ import CamoufoxUpdate
CamoufoxUpdate().update()
print('[camoufox] Done!', flush=True)
