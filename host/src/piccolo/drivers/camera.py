"""
CameraManager — manages a Basler camera via pypylon.

Encapsulates the camera thread, frame grabbing, and settings.
All camera globals from the old piccolo_ui.py live here.
"""

import threading
import time

import numpy as np

# Optional imports — camera support is not required
_CAMERA_LIBS_AVAILABLE = True
_CAMERA_IMPORT_ERROR = None
try:
    from pypylon import pylon
except ImportError as e:
    _CAMERA_LIBS_AVAILABLE = False
    _CAMERA_IMPORT_ERROR = f"pypylon: {e}"

try:
    import cv2
except ImportError as e:
    _CAMERA_LIBS_AVAILABLE = False
    _CAMERA_IMPORT_ERROR = f"opencv: {e}"


class CameraManager:
    """Manages a Basler camera lifecycle and frame streaming."""

    def __init__(self, hw_trigger=False, verbose=True):
        if not _CAMERA_LIBS_AVAILABLE:
            raise ImportError(f"Camera libraries not available: {_CAMERA_IMPORT_ERROR}")

        self.verbose = verbose
        self._hw_trigger = hw_trigger
        self._running = False
        self._thread = None
        self._camera = None

        self._frame_lock = threading.Lock()
        self._camera_lock = threading.Lock()
        self._latest_frame_jpeg = None

        # Create placeholder frame
        placeholder = np.zeros((240, 320, 3), dtype=np.uint8)
        cv2.putText(placeholder, "Waiting for Camera...", (30, 120),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (128, 128, 128), 1)
        ret, jpeg = cv2.imencode('.jpg', placeholder)
        if ret:
            self._latest_frame_jpeg = jpeg.tobytes()

    @property
    def available(self):
        return _CAMERA_LIBS_AVAILABLE

    def start(self):
        """Start the camera grab thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._grab_loop, daemon=True)
        self._thread.start()
        if self.verbose:
            print("[CameraManager] Camera thread started.")

    def stop(self):
        """Stop the camera grab thread and release the camera."""
        if not self._running:
            return
        self._running = False
        if self._thread:
            self._thread.join(timeout=7)
            if self._thread.is_alive():
                print("[CameraManager] Warning: Camera thread did not stop in time.")
        if self.verbose:
            print("[CameraManager] Camera thread stopped.")

    def restart(self, hw_trigger=None):
        """Stop and restart the camera, optionally changing trigger mode."""
        if hw_trigger is not None:
            self._hw_trigger = hw_trigger
        self.stop()
        self.start()

    def get_latest_frame(self):
        """Return the most recent JPEG frame as bytes, or None."""
        with self._frame_lock:
            return self._latest_frame_jpeg

    def set_exposure(self, us):
        """Set camera exposure time in microseconds."""
        with self._camera_lock:
            if self._camera and self._camera.IsOpen():
                self._camera.ExposureTime.SetValue(float(us))

    def set_trigger_delay(self, us):
        """Set camera trigger delay in microseconds."""
        with self._camera_lock:
            if self._camera and self._camera.IsOpen():
                self._camera.TriggerDelay.SetValue(float(us))

    def _grab_loop(self):
        """Camera grab thread — opens camera, grabs frames, encodes JPEG."""
        cam = None
        try:
            cam = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
            cam.Open()

            # Disable auto-features
            cam.ExposureAuto.SetValue("Off")
            cam.GainAuto.SetValue("Off")

            # Sensor config
            cam.Width.SetValue(2048)
            cam.Height.SetValue(2048)
            cam.PixelFormat.SetValue("Mono12p")

            # Trigger config
            mode = "On" if self._hw_trigger else "Off"
            cam.TriggerSelector.SetValue("FrameStart")
            cam.TriggerMode.SetValue(mode)
            cam.TriggerSource.SetValue("Line1")
            if self.verbose:
                print(f"[CameraManager] TriggerMode: {mode}")

            # Initial parameters
            cam.ExposureTime.SetValue(28.0)
            cam.TriggerDelay.SetValue(0.0)

            with self._camera_lock:
                self._camera = cam

            cam.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
            converter = pylon.ImageFormatConverter()
            converter.OutputPixelFormat = pylon.PixelType_BGR8packed

            while cam.IsGrabbing() and self._running:
                try:
                    grab = cam.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
                    if grab.GrabSucceeded():
                        image = converter.Convert(grab)
                        img = image.GetArray()

                        # Resize for web display
                        target_w = 640
                        aspect = img.shape[0] / img.shape[1]
                        target_h = int(target_w * aspect)
                        img_resized = cv2.resize(img, (target_w, target_h))
                        ret, jpeg = cv2.imencode('.jpg', img_resized, [cv2.IMWRITE_JPEG_QUALITY, 75])
                        if ret:
                            with self._frame_lock:
                                self._latest_frame_jpeg = jpeg.tobytes()
                    grab.Release()
                except pylon.GenericException as e:
                    print(f"[CameraManager] Pylon grab error: {e}")
                    time.sleep(0.1)
                except Exception as e:
                    print(f"[CameraManager] Processing error: {e}")
                    time.sleep(0.1)

        except pylon.GenericException as e:
            print(f"[CameraManager] Camera init error: {e}")
            error_img = np.zeros((240, 320, 3), dtype=np.uint8)
            cv2.putText(error_img, "Camera Error", (50, 120),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
            ret, jpeg = cv2.imencode('.jpg', error_img)
            if ret:
                with self._frame_lock:
                    self._latest_frame_jpeg = jpeg.tobytes()
        except Exception as e:
            print(f"[CameraManager] Unexpected error: {e}")
        finally:
            with self._camera_lock:
                self._camera = None
            if cam:
                if cam.IsGrabbing():
                    cam.StopGrabbing()
                if cam.IsOpen():
                    cam.Close()
            if self.verbose:
                print("[CameraManager] Camera released.")
