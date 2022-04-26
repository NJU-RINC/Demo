from baseForm import Ui_Form
from thread_safe_data_structure import WindowSlots

import json
import numpy as np
import cv2, sys, threading, time
from PyQt5 import QtWidgets
from PyQt5.QtGui import QImage, QPixmap
import cv2 as cv
import base64
import requests

cameraMatrix = np.array([[1612.59872732951, -0.322499171177306, 1265.18659717837],
          [0., 1612.15199437803, 708.874191354349],
          [0., 0., 1.]])
distCoeffs = np.array([[-0.443947590101190], [0.245002940770680], [-0.000682381695366930], [-0.00127148900702161], [-0.0734141582733169]])
imageSize = (2560, 1440)

map1, map2 = cv.initUndistortRectifyMap(cameraMatrix, distCoeffs, None, None,
                           # cv.getOptimalNewCameraMatrix(cameraMatrix, distCoeffs, imageSize, 1, imageSize, 0),
                           imageSize, cv.CV_32FC1)


class GWUI(QtWidgets.QWidget, Ui_Form):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

        self.init_button(self.snapshot_button, self.take_snapshot, enable=False)
        self.init_button(self.toggle_button_1, self.toggle_camera, checkable=True)
        self.init_button(self.detect_button_1, self.detect, checkable=True, enable=False)

        self.ip_1 = "rtsp://admin:welcome2rinc@l498b85467.qicp.vip/h265"
        self.baseImg_1 = None

        self.image_slots = WindowSlots(5)
        self.message_slots = WindowSlots(2)
        self.displayer = DisplayerThread(self)
        self.ip_camera = IPCameraThread(self.ip_1, self.image_slots)
        self.post_worker = PostThread(self.image_slots, self.message_slots)

        self.init_camera()

    @staticmethod
    def init_button(button, func, checkable=False, enable=True):
        if checkable:
            button.setCheckable(True)
        if not enable:
            button.setEnabled(False)
        button.clicked.connect(func)

    def init_camera(self):
        self.ip_camera.daemon = True
        self.ip_camera.start()
        self.displayer.daemon = True
        self.displayer.start()
        self.post_worker.daemon = True
        self.post_worker.start()

    def take_snapshot(self):
        frame = self.image_slots.top()
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        self.baseImg_1 = frame
        self.detect_button_1.setEnabled(True)
        post(frame, service_type=1)
        img = QImage(frame.data, frame.shape[1], frame.shape[0], QImage.Format_RGB888)
        self.Image_1.setPixmap(QPixmap.fromImage(img))
        cv2.waitKey(0)

        self.snapshot_button.setText("更新快照")

    def toggle_camera(self, button):
        if button.isChecked():
            button.setText("打开摄像头")
            self.displayer.stop()
            self.snapshot_button.setEnabled(False)
        else:
            button.setText("关闭摄像头")
            self.displayer.restart()
            self.snapshot_button.setEnabled(True)

    def detect(self):
        if self.detect_button_1.isChecked():
            self.detect_button_1.setText("停止检测")
            self.post_worker.restart()
            print("detecting...")
            self.snapshot_button.setEnabled(False)
        else:
            self.detect_button_1.setText("开始检测")
            self.snapshot_button.setEnabled(True)


def set_image(widget, image):
    image = QImage(image.data, image.shape[1], image.shape[0], QImage.Format_RGB888)
    widget.setPixmap(QPixmap.fromImage(image))
    cv2.waitKey(0)


services = ['target_pic', 'base_pic', 'classify_pic']

def post(image, url='http://114.212.85.141:2627', service_type=0, device_id=1):
        payload = {
            "device": device_id,
            "time": "2022-1-1",
            "image_type": service_type, # 0 target 1 base 2 classify
            "image_format": "jpg",
            "image_size": "",
            "image_data": ""
        }

        _, imgbytes = cv.imencode('.jpg', image)
        img_64 = base64.b64encode(imgbytes).decode()
        payload['image_data'] = img_64
        payload['image_size'] = len(imgbytes)

        resp = requests.post(f'{url}/{services[service_type]}', json=payload)

        return json.loads(resp.text)

class PostThread(threading.Thread):
    def __init__(self, imgs: WindowSlots, msgs: WindowSlots):
        super().__init__()
        self.imgs = imgs
        self.msgs = msgs
        self.turn_off = True
        self.lock = threading.Lock()
        self.event = threading.Event()

    def run(self):
        while True:
            self.lock.acquire()
            if not self.turn_off:
                self.lock.release()
                frame = self.imgs.top()
                ret = post(frame)
                self.msgs.push(ret)
                time.sleep(0.1)
            else:
                self.lock.release()
                self.event.wait()

    def stop(self):
        self.lock.acquire()
        self.turn_off = True
        self.lock.release()

    def restart(self):
        self.lock.acquire()
        self.turn_off = False
        self.lock.release()
        self.event.set()


class DisplayerThread(threading.Thread):
    def __init__(self, ui: GWUI):
        super().__init__()
        self.ui = ui
        self.turn_off = False
        self.lock = threading.Lock()
        self.event = threading.Event()

    def run(self):
        while True:
            self.lock.acquire()
            if not self.turn_off:
                self.lock.release()
                frame = self.ui.image_slots.top()
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                ret = self.ui.message_slots.top_unblock()
                if ret != None and ret["code"] == 0:
                    for label in ret["labels"]:
                        left_top = (label["left"], label["top"])
                        right_bottom = (label["right"], label["bottom"])
                        cls = label["cls"]
                        frame = cv.rectangle(frame, left_top, right_bottom, (255, 0, 0), 3)
                        cv.putText(frame, str(cls), left_top, cv.QT_FONT_BLACK, 3, (255, 0, 0), 2, cv2.LINE_AA)
                set_image(self.ui.Video_1, frame)

                if not self.ui.detect_button_1.isChecked():
                    self.ui.snapshot_button.setEnabled(True)

                time.sleep(0.04)
            else:
                self.lock.release()
                self.close()
                self.event.wait()

    def close(self):
        self.ui.snapshot_button.setEnabled(False)
        self.ui.detect_button_1.setEnabled(False)
        frame = np.zeros((1440, 2560, 3), dtype=np.uint8)
        set_image(self.ui.Video_1, frame)

    def stop(self):
        self.lock.acquire()
        self.turn_off = True
        self.lock.release()

    def restart(self):
        self.lock.acquire()
        self.turn_off = False
        self.lock.release()
        self.event.set()


class IPCameraThread(threading.Thread):
    '''
    read image from ip camera and save to the window slots
    '''
    def __init__(self, url, slots: WindowSlots):
        super().__init__()
        self.url = url
        self.slots = slots

    def run(self):
        cap = cv.VideoCapture(self.url)
        success, frame = cap.read()
        if success:
            while cap.isOpened():
                success, frame = cap.read()
                frame = cv.remap(frame, map1, map2, cv.INTER_LINEAR)
                timestamp = int(cap.get(cv2.CAP_PROP_POS_MSEC))
                if success:
                    self.slots.push(frame)

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    mainWindow = GWUI()
    mainWindow.show()
    sys.exit(app.exec())
