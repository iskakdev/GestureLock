import cv2
import mediapipe as mp
import os
import time
from datetime import datetime

password = 8
HOLD_TIME = 1
PHOTO_COUNTDOWN = 3
VIDEO_COUNTDOWN = 5
VIDEO_TIME = 5

cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Камера не найдена")
    exit()

mp_hands = mp.solutions.hands
hands = mp_hands.Hands(max_num_hands=2, min_detection_confidence=0.7, min_tracking_confidence=0.5)
mp_draw = mp.solutions.drawing_utils

os.makedirs("Photos", exist_ok=True)
os.makedirs("Videos", exist_ok=True)

fps = cap.get(cv2.CAP_PROP_FPS) or 30
prev_time = time.time()
fourcc = cv2.VideoWriter_fourcc(*"mp4v")

state = "LOCKED"
action = None
countdown_start = 0
countdown_time = 0

gesture_name = None
gesture_start = 0
gesture_ready = True

video_writer = None
video_start = 0

message = ""
message_time = 0


def distance(a, b):
    return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5


def fingers_up(hand):
    lm = hand.landmark
    thumb = distance(lm[4], lm[17]) > distance(lm[3], lm[17]) and distance(lm[4], lm[5]) > distance(lm[3], lm[5])
    others = [distance(lm[tip], lm[0]) > distance(lm[tip - 2], lm[0]) for tip in (8, 12, 16, 20)]
    return [thumb] + others


def get_gesture(hand):
    lm = hand.landmark
    thumb, index, middle, ring, pinky = fingers_up(hand)

    if thumb and index and middle and ring and pinky:
        return "palm"

    if index and middle and not ring and not pinky:
        return "victory"

    thumb_on_top = lm[4].y < lm[3].y < lm[2].y and lm[4].y < min(p.y for p in lm[5:])
    if thumb and thumb_on_top and not (index or middle or ring or pinky):
        return "like"

    return None


def file_name():
    return datetime.now().strftime("%d_%m_%Y_%H_%M_%S")


def show_message(text):
    global message, message_time
    message = text
    message_time = time.time()


def draw_text(frame, text, x, y, scale, color, thickness):
    cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), thickness + 6)
    cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness)


def draw_text_center(frame, text, y, scale, color, thickness):
    (w, h), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness)
    draw_text(frame, text, (frame.shape[1] - w) // 2, y, scale, color, thickness)


while True:
    ret, frame = cap.read()

    if not ret:
        print("Нет кадра")
        break

    now = time.time()
    fps = fps * 0.9 + 0.1 / max(now - prev_time, 0.001)
    prev_time = now

    frame = cv2.flip(frame, 1)
    clean_frame = frame.copy()

    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(rgb_frame)

    total_fingers = 0
    gesture = None

    if results.multi_hand_landmarks:
        for hand in results.multi_hand_landmarks:
            mp_draw.draw_landmarks(frame, hand, mp_hands.HAND_CONNECTIONS)
            total_fingers += sum(fingers_up(hand))

        if len(results.multi_hand_landmarks) == 1:
            gesture = get_gesture(results.multi_hand_landmarks[0])
    else:
        gesture_ready = True

    if video_writer:
        video_writer.write(clean_frame)

        if time.time() - video_start >= VIDEO_TIME:
            video_writer.release()
            video_writer = None
            show_message("Video saved")
            print("Видео сохранено")

    if state == "LOCKED":
        current = "password" if total_fingers == password else None
    elif state == "UNLOCKED" and gesture_ready and not video_writer:
        current = gesture
    else:
        current = None

    if current != gesture_name:
        gesture_name = current
        gesture_start = time.time()

    hold = time.time() - gesture_start if gesture_name else 0

    if gesture_name and hold >= HOLD_TIME:
        gesture_name = None
        gesture_ready = False

        if current == "password":
            state = "UNLOCKED"
            show_message("Unlocked")
            print("Доступ открыт")

        elif current == "victory":
            state = "COUNTDOWN"
            action = "photo"
            countdown_time = PHOTO_COUNTDOWN
            countdown_start = time.time()

        elif current == "like":
            state = "COUNTDOWN"
            action = "video"
            countdown_time = VIDEO_COUNTDOWN
            countdown_start = time.time()

        elif current == "palm":
            print("Выход")
            break

    if state == "COUNTDOWN":
        left = countdown_time - int(time.time() - countdown_start)

        if left <= 0:
            if action == "photo":
                name = f"Photos/{file_name()}.jpg"
                cv2.imwrite(name, clean_frame)
                show_message("Photo saved")
                print(f"Фото сохранено: {name}")
            else:
                name = f"Videos/{file_name()}.mp4"
                video_writer = cv2.VideoWriter(name, fourcc, round(fps), (clean_frame.shape[1], clean_frame.shape[0]))
                video_start = time.time()
                show_message("Recording")
                print(f"Запись видео: {name}")

            state = "UNLOCKED"
        else:
            draw_text_center(frame, str(left), frame.shape[0] // 2 + 60, 6, (0, 255, 255), 12)

    colors = {"LOCKED": (0, 0, 255), "UNLOCKED": (0, 255, 0), "COUNTDOWN": (0, 255, 255)}
    draw_text(frame, state, 20, 45, 1, colors[state], 2)
    draw_text(frame, f"Fingers: {total_fingers}", 20, 85, 1, (255, 255, 255), 2)

    if gesture_name:
        bar = int(min(hold / HOLD_TIME, 1) * 200)
        cv2.rectangle(frame, (20, 100), (20 + bar, 108), colors[state], cv2.FILLED)

    if state == "UNLOCKED" and not video_writer:
        hint = "V - photo   Like - video   Palm - exit"
        if not gesture_ready:
            hint = "Remove hand"
        draw_text(frame, hint, 20, frame.shape[0] - 20, 0.7, (255, 255, 255), 2)

    if state == "LOCKED":
        draw_text(frame, f"Show {password} fingers", 20, frame.shape[0] - 20, 0.7, (255, 255, 255), 2)

    if video_writer:
        left = VIDEO_TIME - int(time.time() - video_start)
        cv2.circle(frame, (frame.shape[1] - 40, 40), 12, (0, 0, 255), cv2.FILLED)
        draw_text(frame, f"REC {left}", frame.shape[1] - 150, 50, 0.8, (0, 0, 255), 2)

    if message and time.time() - message_time < 2:
        draw_text_center(frame, message, 150, 1, (255, 255, 255), 2)

    cv2.imshow("Gesture Lock", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

if video_writer:
    video_writer.release()

cap.release()
cv2.destroyAllWindows()

