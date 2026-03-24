"""下载 Camoufox 浏览器二进制文件（支持 GitHub 代理加速）

直接 patch requests.get，在最底层拦截所有 GitHub HTTP 请求。
"""
import requests

_original_get = requests.get

def _proxied_get(url, **kwargs):
    if isinstance(url, str) and 'github.com' in url:
        proxies = [
            ('ghfast.top', url.replace('https://github.com', 'https://ghfast.top/https://github.com')),
            ('ghgo.xyz', url.replace('https://github.com', 'https://ghgo.xyz/https://github.com')),
        ]
        for name, proxy_url in proxies:
            print(f'[camoufox] Trying {name}: {proxy_url}', flush=True)
            try:
                resp = _original_get(proxy_url, **kwargs)
                resp.raise_for_status()
                return resp
            except Exception as e:
                print(f'[camoufox] {name} failed: {e}', flush=True)
        print(f'[camoufox] All proxies failed, direct: {url}', flush=True)
    return _original_get(url, **kwargs)

requests.get = _proxied_get

from camoufox.__main__ import CamoufoxUpdate
CamoufoxUpdate().update()
print('[camoufox] Done!', flush=True)
