"""下载 Camoufox 浏览器二进制文件（支持 GitHub 代理加速）"""
from camoufox.__main__ import CamoufoxUpdate

# 在 CamoufoxUpdate 实例创建后，直接替换 self.url 里的 github.com
_original_install = CamoufoxUpdate.install

def _patched_install(self):
    """替换下载 URL 为代理地址"""
    if hasattr(self, 'url') and self.url and 'github.com' in self.url:
        original_url = self.url
        self.url = original_url.replace('https://github.com', 'https://ghgo.xyz/https://github.com')
        print(f'[fetch_camoufox] Proxy URL: {self.url}', flush=True)
        try:
            return _original_install(self)
        except Exception as e:
            print(f'[fetch_camoufox] ghgo.xyz failed: {e}', flush=True)
            self.url = original_url.replace('https://github.com', 'https://ghfast.top/https://github.com')
            print(f'[fetch_camoufox] Trying ghfast.top: {self.url}', flush=True)
            try:
                return _original_install(self)
            except Exception as e2:
                print(f'[fetch_camoufox] ghfast.top failed: {e2}', flush=True)
                self.url = original_url
                print(f'[fetch_camoufox] Direct: {self.url}', flush=True)
                return _original_install(self)
    return _original_install(self)

CamoufoxUpdate.install = _patched_install

CamoufoxUpdate().update()
print('[fetch_camoufox] Done!', flush=True)
