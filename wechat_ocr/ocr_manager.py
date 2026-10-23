import os
import time
from enum import Enum
from typing import Dict, Callable
from multiprocessing import Queue, Value

from . import ocr_wx4_pb2
from .winapi import *
from .mmmojo_dll import MMMojoInfoMethod
from .xplugin_manager import XPluginManager
from .config import resolve

OCR_MAX_TASK_ID = 32


class RequestIdOCR(Enum):
    """微信 4.x OCR 组件的请求/响应 ID (见 mmmojo 的 RequestIdOCR4)"""
    HAND_SHAKE = 10001
    REQ_OCR = 10010
    RESP_OCR = 10011


# 兼容旧接口: 导入时尝试用默认规则解析出路径, 失败则为 None (可由配置文件/环境变量补救)
try:
    _default_paths = resolve()
    OCR_DEFAULT_EXE_PATH = _default_paths["ocr_exe_path"]
    OCR_DEFAULT_USER_LIB_DIR = _default_paths["wechat_dir"]
except Exception:
    OCR_DEFAULT_EXE_PATH = None
    OCR_DEFAULT_USER_LIB_DIR = None


def OCRRemoteOnConnect(is_connected:c_bool, user_data:py_object):
    print(f"OCRRemoteOnConnect 回调函数被调用, 参数, is_connected: {is_connected}")
    if user_data:
        manager_obj:OcrManager = cast(user_data, py_object).value
        manager_obj.SetConnectState(True)

def OCRRemoteOnDisConnect(user_data:py_object):
    print(f"OCRRemoteOnDisConnect 回调函数被调用 ")
    if user_data:
        manager_obj:OcrManager = cast(user_data, py_object).value
        manager_obj.SetConnectState(False)

def OCRReadOnPush(request_id:c_uint32, request_info:c_void_p, user_data:py_object):
    print(f"OCRReadOnPush 回调函数被调用 参数, request_id: {request_id}, request_info: {request_info}")
    if user_data:
        manager_obj:OcrManager = cast(user_data, py_object).value
        pb_size = c_uint32()
        pb_data = manager_obj.GetPbSerializedData(request_info, pb_size)
        if pb_size.value > 10:
            print(f"正在解析pb数据，pb数据大小: {pb_size.value}")
            manager_obj.CallUsrCallback(request_id, pb_data, pb_size.value)
            manager_obj.RemoveReadInfo(request_info)


class OcrManager(XPluginManager):
    m_task_id = Queue(OCR_MAX_TASK_ID)
    m_id_path:Dict[int, str] = {}
    m_usr_lib_dir: str = None
    m_wechatocr_running: bool = False
    m_connect_state:Value = Value('b', False)
    m_usr_callback: Callable = None

    def __init__(self, wechat_path=None) -> None:
        super().__init__(wechat_path)
        self.m_usr_lib_dir = self.m_wechat_dir
        for i in range(1, 33):
            self.m_task_id.put(i)

    def __del__(self):
        if self.m_wechatocr_running:
            self.KillWeChatOCR()

    def SetUsrLibDir(self, usr_lib_dir:str):
        self.m_usr_lib_dir = usr_lib_dir
        self.AppendSwitchNativeCmdLine("user-lib-dir", usr_lib_dir)

    def SetOcrResultCallback(self, func:Callable):
        self.m_usr_callback = func

    def StartWeChatOCR(self):
        self.SetCallbackUsrData(self)
        self.InitMMMojoEnv()
        self.m_wechatocr_running = True

    def KillWeChatOCR(self):
        self.m_connect_state.value = False
        self.m_wechatocr_running = False
        self.StopMMMojoEnv()

    def DoOCRTask(self, pic_path:str):
        if not self.m_wechatocr_running:
            raise Exception("请先调用StartWeChatOCR启动")
        if not os.path.exists(pic_path):
            raise Exception(f"给定图片路径pic_path不存在: {pic_path}")
        # wx4 中，图片路径必须是绝对路径，否则会失败
        pic_path = os.path.abspath(pic_path)
        while not self.m_connect_state.value:
            print("等待Ocr服务连接成功!")
            time.sleep(1)
        _id = self.GetIdleTaskId()
        if not _id:
            print("当前队列已满，请等待后重试")
            return
        self.SendOCRTask(_id, pic_path)

    def SetConnectState(self, connect:bool):
        self.m_connect_state.value = connect

    def SendOCRTask(self, task_id:int, pic_path:str):
        self.m_id_path[task_id] = pic_path
        # 微信 4.x 协议: ParseOCRReqMessage
        ocr_request = ocr_wx4_pb2.ParseOCRReqMessage()
        ocr_request.task_id = task_id
        ocr_request.pic_path = pic_path
        # 字段含义未完全确认, 但置位 t1/t2 是识别成功的前提 (与微信4.x行为一致)
        ocr_request.rt.t1 = True
        ocr_request.rt.t2 = True
        ocr_request.rt.t3 = False
        serialized_data = ocr_request.SerializeToString()
        self.SendPbSerializedData(serialized_data, len(serialized_data), MMMojoInfoMethod.kMMPush.value, 0, RequestIdOCR.REQ_OCR.value)

    def CallUsrCallback(self, request_id:c_uint32, serialized_data: c_void_p, data_size: int):
        ocr_response_ubyte = (c_ubyte * data_size).from_address(serialized_data)
        ocr_response = ocr_wx4_pb2.ParseOCRRespMessage()
        ocr_response.ParseFromString(bytearray(ocr_response_ubyte))
        task_id = ocr_response.task_id
        pic_path = self.m_id_path.get(task_id)
        if pic_path is None:
            return
        if self.m_usr_callback:
            self.m_usr_callback(pic_path, self.parse_ocr_response(ocr_response))
        self.SetTaskIdIdle(task_id)

    @staticmethod
    def parse_ocr_response(ocr_response) -> dict:
        """把微信 4.x 的 ParseOCRRespMessage 转成结果 dict。

        结构与旧版 (3.x) 保持基本一致, 方便下游代码迁移:
            {"taskId", "errcode", "width", "height",
             "ocrResult": [{"text", "rate", "location": {"left","top","right","bottom"}}]}
        """
        results = {
            "taskId": ocr_response.task_id,
            "errcode": ocr_response.err_code,
            "ocrResult": []
        }
        if not ocr_response.HasField("res"):
            return results
        results["width"] = ocr_response.res.img_width
        results["height"] = ocr_response.res.img_height
        for line in ocr_response.res.lines:
            results["ocrResult"].append({
                "text": line.text,
                "rate": line.rate,
                "location": {
                    "left": line.left,
                    "top": line.top,
                    "right": line.right,
                    "bottom": line.bottom,
                },
            })
        return results

    def GetIdleTaskId(self):
        task_id = self.m_task_id.get(timeout=1)
        return task_id

    def SetTaskIdIdle(self, _id):
        self.m_task_id.put(_id)

    def SetDefaultCallbaks(self):
        super().SetOneCallback("kMMRemoteConnect", OCRRemoteOnConnect)
        super().SetOneCallback("kMMRemoteDisconnect", OCRRemoteOnDisConnect)
        super().SetOneCallback("kMMReadPush", OCRReadOnPush)
        super().SetDefaultCallbaks()
