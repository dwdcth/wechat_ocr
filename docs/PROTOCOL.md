# wechat_ocr 协议参考与升级复验手册

> 本文是 mmmojo OCR 协议的**唯一事实源**（代码常量、`tools/verify_protocol.py`
> 探针均以此为纲）。逆向验证于 **wechat-universal 4.1.13.26 (Linux)**；
> 微信更新后请先跑自检工具，失败项按本文「升级复验步骤」重推。

## 1. 传输层（libmmmojo）

宿主（本进程）通过 `libmmmojo.so` 与 wxocr 子进程 IPC：

```
CreateMMMojoEnvironment → SetMMMojoEnvironmentCallbacks(8 槽位)
  → SetMMMojoEnvironmentInitParams(kMMHostProcess=1, kMMExePath=wxocr)
  → [Linux/macOS 追加 no-sandbox 开关]
  → StartMMMojoEnvironment → 子进程回 10001 握手 → kMMRemoteConnect
```

写消息：`CreateMMMojoWriteInfo(method, sync, request_id)` →
`GetMMMojoWriteInfoRequest(wi, size)`（主缓冲区）/ `GetMMMojoWriteInfoAttach(wi,
size)`（附加缓冲区）→ `SendMMMojoWriteInfo`。
读消息：回调按 method 分流到 `kMMReadPush / kMMReadPull / kMMReadShared`，
载荷 = `GetMMMojoReadInfoRequest`（+ attach：`GetMMMojoReadInfoAttach`）。

## 2. OCR 组件消息（request_id ↔ 名称，逆向自 libwxocr.so 日志表）

| id | 名称 | 方向/方法 |
|---|---|---|
| 10001 | SET_USER_INFO（握手） | 子进程 → 宿主 Push |
| 10010 | PARSEOCR_INFO_REQ | 宿主 → 子进程 **kMMPush** |
| 10011 | PARSEOCR_INFO_RESP | 子进程 → 宿主 Push（所有响应都走它） |
| 10018 | PARSEOCR_INFO_REQ_SHARED | 宿主 → 子进程 **kMMShared** |

其余族内消息（未使用）：10012/10013 GENERATE_INFO_QR_*（生码）、
10014/10015 PARSEAI_INFO_*、10016 BENCHMARK_INFO_RESP、10017 CONFIG_OCR_REQ、
10019 GENERATE_INFO_QR_REQ。

## 3. 路径版请求（10010, kMMPush）

`ParseOCRReqMessage`（见 `proto/ocr_wx4.proto`）：

```proto
{ task_id: varint, pic_path: string, xx3/xx4: 死字段, pic_data: 死字段,
  rt: {t1=true, t2=true, t3=false} }
```

- 处理器只读 `pic_path`：open → size → read → 解码 → OCR；`pic_data/xx3/xx4`
  从未被访问（死字段）
- **错误行为（4.1.13 实测）**：空路径/不存在的路径 → **任务静默丢弃**
  （无响应、连接存活）；代码内存在 err=2（pb 解析失败）/err=4（size<0）/
  err=5（短读）分支，但 4.1.13 Linux 上路径错误走不到（上游 swigger 观察到的
  err=4 是老版本语义）
- task_id ∈ 1..32（并发队列），响应回带同 task_id

## 4. 零拷贝版请求（10018, kMMShared）——微信自身截图同款

- **request 缓冲区** = RGBA8888 原始像素，长度 `width*height*4`
- **attach 缓冲区** = `ParseOCRReqSharedMessage`（手写 pb，见
  `ocr_manager.shared_ocr_meta_pb`）：

```proto
{ 1: pic_path(可空), 2: width varint, 3: height varint,
  4: rt {t1=true, t2=true} }
```

- sync=false；**响应仍是普通 10011 推送，task_id 恒为 0**（无关联字段 →
  同刻只能一个在途）
- ⚠ 载荷错误（尺寸不符/字段错位）会**打断 mojo 连接**（子进程侧无容错）

## 5. 响应（10011）

`ParseOCRRespMessage`：`{task_id, err_code, res{lines[]{text, rate,
left/top/right/bottom}, img_width/height}, qrcode[]{text, type, corners×4}}`

- `rate` 恒 ∈ [0,1]（4.1.13 实测同图多次识别完全确定性）
- 码类型：`19`=QR_CODE（text=解码内容）、`22`=VQR_CODE（**小程序码**，
  text=原始载荷，跳转需微信服务端解析）；条形码数字走 `lines` 文字行

## 6. 升级复验步骤（微信大版本更新后）

按序执行，哪步挂了就重推哪步（工具 `tools/verify_protocol.py` 对应 P1-P9）：

| 探针 | 验证点 | 失败时的重推锚点 |
|---|---|---|
| P1 路径解析 | 微信安装目录/可执行名变化 | `config.py` 候选表；`ls /opt/wechat*` |
| P2 握手 | mmmojo 传输层 | 换了 IPC 机制则全协议重推 |
| P3 路径版识别 | 10010 + pic_path + rt{t1,t2} | 若 err≠0：wxocr 处理器字段变了 |
| P4 坏路径行为 | 空路径/坏路径 → 静默丢弃且连接存活 | 若变为有响应/断连 = 处理器语义漂移 |
| P5 零拷贝识别 | 10018 + attach 元数据 + RGBA | 若断连：载荷布局变了 |
| P6 码识别 | qrcode type 19/22 | QBar 模型输出格式 |
| P7 bytes 临时文件 | DoOCRTaskData 链路 | 同 P3 |
| P8 协议异步 | 批量 + WaitDone | 任务队列容量/回带 id |
| P9 版本探测 | detect_wechat_version | 版本串位置漂移 |

**静态重推手法**（详见 rumi 仓库 `docs/开发经验.md` §七）：

1. `strings -a libwxocr.so | grep -i vqr/qbar/zxing` —— 确认引擎结构还在
2. id→名称日志表：找 `movl $0x2722/%eax` 类常量存取的静态初始化函数，
   读表内 {id, 字符串指针, 长度} 三元组
3. 10010 处理器：`GetMMMojoReadInfoRequest` 调用者中 open/read 流的那个
4. 10018 处理器：`GetMMMojoReadInfoAttach` 调用者；视图构造的 fmt 位运算
   （`((fmt>>3&0x1ff)+1) × (0x28442211>>((fmt&7)*2)&0xf)` 展开验证 bpp）
5. 主程序发送方：E8-rel32 扫描 `GetMMMojoWriteInfoAttach` 的 PLT 调用点，
   读 `CreateMMMojoWriteInfo(method, sync, id, sizes)` 实参
6. 元数据字段号：发送方序列化函数里的 tag 常量（0x10=field2, 0x18=field3…）

黑盒判别实验（不用反汇编）：

- path=A + data=B 同发 → 返回 A 则"带路径无视 data"仍成立
- 故意坏载荷 → 有 err 响应说明消息到了处理器；**断连说明载荷 malformed**
  （"沉默"≠"不支持"）

## 7. 已验证版本

| 微信版本 | 平台 | 状态 |
|---|---|---|
| 4.1.13.26 | Linux (wechat-universal) | ✅ 全探针通过（P1-P9） |

新版本验证通过后请把 `ocr_manager.PROTOCOL_VERIFIED_VERSION`、本表、
探针基线一起更新。
