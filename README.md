## 项目说明
本项目是使用Python来调用微信本地ocr模型，调用方法完全由[QQImpl](https://github.com/EEEEhex/QQImpl)翻译过来。也就是说该项目只是将原C++代码翻译成了纯Python实现。

**现已支持跨平台**: Windows / Linux / macOS (统一使用微信 4.x 协议)。

**支持能力**: 文字识别 (OCR) + 二维码识别 (内容与角点坐标) + 敏感信息打码。

#### 温馨提示

该项目自己玩玩就行，不要用于商业用途

## 使用说明

#### 安装

本项目未发布到 PyPI, 请直接从 GitHub 安装:

```bash
# pip
pip install git+https://github.com/dwdcth/wechat_ocr.git
# 或 uv
uv pip install git+https://github.com/dwdcth/wechat_ocr.git
# 或作为项目依赖 (pyproject.toml)
#   dependencies = ["wechat-ocr @ git+https://github.com/dwdcth/wechat_ocr.git"]
uv add git+https://github.com/dwdcth/wechat_ocr
```

也可以不安装直接运行:

```bash
uv run --with git+https://github.com/dwdcth/wechat_ocr --with protobuf python your_script.py
```

#### 依赖(必要条件)

1. Windows / Linux / macOS 系统
2. 已安装微信 4.x (Linux 为 wechat-universal 等发行版, macOS 为 WeChat.app)
3. Python 3.12+, 以及 `protobuf`

#### 微信路径解析

库会按以下顺序解析微信安装路径 (即包含 `mmmojo` 动态库与 `WeChatOCR`/`wxocr` 可执行文件的目录):

1. **显式传参**: `OcrManager(wechat_path)`
2. **环境变量**: `WECHAT_OCR_DIR` / `WECHAT_OCR_EXE` / `WECHAT_OCR_MMMOJO`
3. **配置文件** (JSON):
   - Linux/macOS: `~/.config/wechat_ocr/config.json` (或 `$XDG_CONFIG_HOME/wechat_ocr/config.json`)
   - Windows: `%APPDATA%\wechat_ocr\config.json`
   - 可用环境变量 `WECHAT_OCR_CONFIG` 直接指定配置文件完整路径

   ```json
   {
       "wechat_dir": "/opt/wechat-universal",
       "ocr_exe_path": "/opt/wechat-universal/wxocr",
       "mmmojo_path": "/opt/wechat-universal/libmmmojo.so"
   }
   ```

   只填 `wechat_dir` 即可，其余两项会在该目录下自动查找。
4. **常见路径自动探测**:
   - Windows: `C:\Program Files\Tencent\WeChat` 等
   - Linux: `/opt/wechat-universal`、`/opt/wechat` 等
   - macOS: `/Applications/WeChat.app`

#### 示例

```python
import os
import json
import time
from wechat_ocr.ocr_manager import OcrManager, OCR_MAX_TASK_ID


def ocr_result_callback(img_path:str, results:dict):
    result_file = os.path.basename(img_path) + ".json"
    print(f"识别成功，img_path: {img_path}, result_file: {result_file}")
    with open(result_file, 'w', encoding='utf-8') as f:
       f.write(json.dumps(results, ensure_ascii=False, indent=2))

def main():
    # 微信路径解析顺序: 显式传参 > 环境变量 > 配置文件 > 自动探测
    #   - Windows: OcrManager(r"C:\Program Files\Tencent\WeChat")
    #   - Linux:   OcrManager("/opt/wechat-universal")
    #   - macOS:   OcrManager("/Applications/WeChat.app")
    ocr_manager = OcrManager()
    # 设置ocr识别结果的回调函数
    ocr_manager.SetOcrResultCallback(ocr_result_callback)
    # 启动ocr服务
    ocr_manager.StartWeChatOCR()
    # 开始识别图片
    ocr_manager.DoOCRTask("test_img/1.png")
    ocr_manager.DoOCRTask("test_img/2.png")
    ocr_manager.DoOCRTask("test_img/3.png")
    # 等待全部任务完成
    while ocr_manager.m_task_id.qsize() != OCR_MAX_TASK_ID:
        time.sleep(0.1)
    # 识别输出结果
    ocr_manager.KillWeChatOCR()


if __name__ == "__main__":
    main()
```

#### 敏感信息打码

基于识别结果对手机号 / 身份证 / 邮箱 / 二维码等区域自动打码 (纯 Pillow 实现):

```bash
# 安装 (含打码依赖 Pillow)
pip install "wechat-ocr[mosaic] @ git+https://github.com/dwdcth/wechat_ocr.git"
```

```python
import time
from wechat_ocr.ocr_manager import OcrManager, OCR_MAX_TASK_ID
from wechat_ocr.mosaic import apply_mosaic

results = {}
ocr_manager = OcrManager()
ocr_manager.SetOcrResultCallback(lambda p, r: results.update(r))
ocr_manager.StartWeChatOCR()
ocr_manager.DoOCRTask("screenshot.png")
while ocr_manager.m_task_id.qsize() != OCR_MAX_TASK_ID:
    time.sleep(0.1)
ocr_manager.KillWeChatOCR()

img = apply_mosaic(
    "screenshot.png", results,
    patterns="default",   # 内置正则: 手机号/身份证/邮箱; 也可传自定义正则列表
    qrcode=True,          # 二维码区域一并打掉
    style="pixel",        # pixel 马赛克 | blur 高斯模糊 | solid 纯色
)
img.save("masked.png")
```

完整示例见 `example/mosaic.py`。

#### 运行结果

![result](./result.png)

#### 识别结果格式 (微信 4.x 协议)

```json
{
  "taskId": 2,
  "errcode": 0,
  "width": 300,
  "height": 60,
  "ocrResult": [
    {
      "text": "你好世界",
      "rate": 0.99,
      "location": {"left": 8.0, "top": 18.0, "right": 202.0, "bottom": 52.0}
    }
  ],
  "qrcode": [
    {
      "text": "https://github.com/dwdcth",
      "type": 19,
      "corners": {
        "topleft": {"x": 33.0, "y": 34.0},
        "topright": {"x": 247.0, "y": 34.0},
        "bottomright": {"x": 247.0, "y": 248.0},
        "bottomleft": {"x": 33.0, "y": 248.0}
      }
    }
  ]
}
```

说明:
- `ocrResult`: 文字识别结果; 条形码 (EAN-13 等) 的数字也会作为文本行出现在这里
- 识别文本中 OCR 偶有漏字 (如身份证末位), 打码区域按整行文本框处理, 不影响遮盖效果
- `qrcode`: 二维码识别结果, 仅当图片中含二维码时返回; `type=19` 为 QR_CODE,
  `corners` 为四个角点像素坐标, 可用于打码/贴图处理
- 一张图可同时返回文字与多个二维码

> 注: 本版本统一使用微信 4.x 的 `ParseOCRReqMessage/ParseOCRRespMessage` 协议
> (request id: 10010/10011), 不再支持微信 3.x 的旧协议。
> 请求中的 `pic_data` 字段实测无法单独使用 (返回 err=4), 请始终使用 `pic_path` 传图片绝对路径。

## 感谢

https://github.com/EEEEhex/QQImpl
https://github.com/swigger/wechat-ocr (Linux/macOS 协议参考)
