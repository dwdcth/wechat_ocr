#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_protocol —— 微信 OCR 协议黑盒自检 (微信升级后先跑这个)。

对应 docs/PROTOCOL.md §6 的 P1-P9 探针。任一失败即协议有漂移,
按 PROTOCOL.md 对应行的「重推锚点」排查。

用法: PYTHONPATH=.. python3 tools/verify_protocol.py [--quick]
  --quick  跳过 P6 码识别/P9 版本探测等非核心项
退出码: 0 全过; 1 有失败项。
"""
import argparse
import io
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from wechat_ocr import config
from wechat_ocr.ocr_manager import (OCR_MAX_TASK_ID, PROTOCOL_VERIFIED_VERSION,
                                    OcrManager, QRCODE_TYPE_NAMES)

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
TEST_DIR = os.path.join(ROOT, "test_img")

RESULTS = []


def probe(name):
    def deco(fn):
        fn._name = name
        RESULTS.append(fn)
        return fn
    return deco


def expect_text(r, keyword):
    """结果里应能找到关键词 (OCR 文本允许小差异)。"""
    joined = "".join(l["text"] for l in r.get("ocrResult", []))
    return keyword in joined


# ── P1: 路径解析 ────────────────────────────────────────────────
@probe("P1 路径解析")
def p1():
    paths = config.resolve()
    assert os.path.isfile(paths["ocr_exe_path"]), f"OCR 可执行不存在: {paths['ocr_exe_path']}"
    assert os.path.isfile(paths["mmmojo_path"]), f"mmmojo 库不存在: {paths['mmmojo_path']}"
    return f"wechat_dir={paths['wechat_dir']} (来源: {paths['source']})"


# ── P2-P8: 引擎探针 (共用一个实例) ──────────────────────────────
class Engine:
    def __init__(self):
        self.results = []      # [(path, result)]
        self.disconnected = False
        self.mgr = OcrManager()

        def cb(path, r):
            self.results.append((path, r))

        def on_disc(*a):
            self.disconnected = True

        self.mgr.SetOneCallback("kMMRemoteDisconnect", on_disc)
        self.mgr.SetOcrResultCallback(cb)

    def start(self, timeout=20):
        self.mgr.StartWeChatOCR()
        self.mgr._wait_connected(timeout=timeout)

    def wait_one(self, timeout=20):
        n0 = len(self.results)
        t0 = time.time()
        while len(self.results) == n0 and time.time() - t0 < timeout:
            time.sleep(0.1)
        if len(self.results) == n0:
            raise TimeoutError(f"{timeout}s 无回调"
                               + ("（且 mojo 已断连——载荷格式变了）" if self.disconnected else ""))
        return self.results[-1][1]


@probe("P2 握手/连接")
def p2(eng):
    eng.start()
    assert eng.mgr.m_connect_state.value, "未进入连接态"
    return "connected"


@probe("P3 路径版识别(10010)")
def p3(eng):
    eng.mgr.DoOCRTask(os.path.join(TEST_DIR, "1.png"))
    r = eng.wait_one()
    assert r["errcode"] == 0, f"errcode={r['errcode']}"
    assert expect_text(r, "GitLab"), "文本不符"
    rates = [l["rate"] for l in r["ocrResult"]]
    assert all(0.0 <= x <= 1.0 for x in rates), f"rate 越界: {rates}"
    return f"{len(r['ocrResult'])}行 rate∈[{min(rates):.3f},{max(rates):.3f}]"


@probe("P4 坏路径行为(4.1.13=静默丢弃)")
def p4(eng):
    n0 = len(eng.results)
    from wechat_ocr.mmmojo_dll import MMMojoInfoMethod
    from wechat_ocr.ocr_manager import RequestIdOCR, ocr_wx4_pb2
    for path in ("", "/nonexistent/__probe__.png"):
        req = ocr_wx4_pb2.ParseOCRReqMessage()
        req.task_id = 31
        req.pic_path = path
        req.rt.t1 = True
        req.rt.t2 = True
        sd = req.SerializeToString()
        eng.mgr.m_id_path[31] = "P4"
        eng.mgr.SendPbSerializedData(sd, len(sd), MMMojoInfoMethod.kMMPush.value, 0,
                                     RequestIdOCR.REQ_OCR.value)
    t0 = time.time()
    while len(eng.results) == n0 and time.time() - t0 < 6:
        time.sleep(0.1)
    assert len(eng.results) == n0, \
        f"4.1.13 基线为静默丢弃, 现在收到了响应 (错误码语义漂移): {eng.results[-1][1]['errcode']}"
    assert eng.mgr.m_connect_state.value, "坏路径导致断连 (处理器行为漂移)"
    return "空路径/坏路径 → 无响应且连接存活 ✓"


@probe("P5 零拷贝识别(10018 Shared)")
def p5(eng):
    from PIL import Image
    img = Image.open(os.path.join(TEST_DIR, "1.png")).convert("RGBA")
    eng.mgr.DoOCRTaskShared(img.tobytes(), *img.size)
    r = eng.wait_one()
    assert r["errcode"] == 0, f"errcode={r['errcode']}"
    assert expect_text(r, "GitLab"), "文本不符"
    assert not eng.disconnected, "mojo 断连 (Shared 载荷布局漂移)"
    return "RGBA → 识别成功, 连接存活"


@probe("P6 码识别(type 19/22)")
def p6(eng):
    eng.mgr.DoOCRTask(os.path.join(TEST_DIR, "qrcode.png"))
    r = eng.wait_one()
    qrs = r.get("qrcode") or []
    assert qrs and qrs[0]["type"] == 19 and "github.com" in qrs[0]["text"], \
        f"QR 识别异常: {qrs}"
    wx = os.path.join(TEST_DIR, "wxacode.png")
    if os.path.isfile(wx):
        eng.mgr.DoOCRTask(wx)
        r2 = eng.wait_one()
        qrs2 = r2.get("qrcode") or []
        assert qrs2 and qrs2[0]["type"] == 22, f"小程序码识别异常: {qrs2}"
        return f"QR(19)+小程序码(22) ✓ payload={qrs2[0]['text']!r}"
    return "QR(19) ✓ (无 wxacode.png, 跳过 22)"


@probe("P7 bytes临时文件链路")
def p7(eng):
    data = open(os.path.join(TEST_DIR, "2.png"), "rb").read()
    eng.mgr.DoOCRTaskData(data)
    r = eng.wait_one()
    assert r["errcode"] == 0 and expect_text(r, "OCR"), "bytes 链路异常"
    leftover = [f for f in os.listdir(tempfile_dir()) if f.startswith("wechat_ocr_")]
    assert not leftover, f"临时文件未清理: {leftover}"
    return "识别 ✓ 临时文件已清理 ✓"


def tempfile_dir():
    import tempfile
    return tempfile.gettempdir()


@probe("P8 协议异步(批量+WaitDone)")
def p8(eng):
    paths = [os.path.join(TEST_DIR, n) for n in ("1.png", "2.png", "3.png")]
    eng.mgr.DoOCRTasks(paths)
    assert 0 < eng.mgr.PendingCount() <= OCR_MAX_TASK_ID + 1, "在途计数异常"
    assert eng.mgr.WaitDone(timeout=30), "WaitDone 超时"
    return "批量提交 → 回调齐 → WaitDone ✓"


@probe("P9 版本探测")
def p9():
    v = config.detect_wechat_version()
    return f"探测到微信版本: {v} (协议验证基线: {PROTOCOL_VERIFIED_VERSION})"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="跳过非核心探针")
    args = ap.parse_args()

    print(f"wechat_ocr 协议自检 (验证基线: {PROTOCOL_VERIFIED_VERSION})")
    print("=" * 60)
    fails = 0
    eng = None
    for fn in RESULTS:
        name = fn._name
        if args.quick and name.split()[0] in ("P6", "P9"):
            print(f"SKIP {name}")
            continue
        t0 = time.time()
        try:
            if name.startswith(("P2", "P3", "P4", "P5", "P6", "P7", "P8")):
                if eng is None:
                    eng = Engine()
                out = fn(eng)
            else:
                out = fn()
            print(f"PASS {name}  ({time.time()-t0:.1f}s)  {out}")
        except Exception as e:
            fails += 1
            print(f"FAIL {name}  ({time.time()-t0:.1f}s)  {e}")
            print(f"     → 见 docs/PROTOCOL.md §6 该行「重推锚点」")
    if eng is not None:
        try:
            eng.mgr.KillWeChatOCR()
        except Exception:
            pass
    print("=" * 60)
    print(f"结果: {'全部通过' if fails == 0 else f'{fails} 项失败'}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
