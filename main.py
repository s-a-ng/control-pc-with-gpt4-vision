import os
import time
import pyautogui
from PIL import Image
import base64
import json, re
import keyboard
import requests

os.system("cls")

SCREEN_X = 1920
SCREEN_Y = 1080

DOWNSCALE_FACTOR = 4

LOWX = int(SCREEN_X/DOWNSCALE_FACTOR)
LOWY = int(SCREEN_Y/DOWNSCALE_FACTOR)

def remove_comments(json_string):
    pattern = re.compile(r'//.*?(?=\n|$)')
    without_comments = re.sub(pattern, '', json_string)
    return without_comments

def extract_json(text):
    json_start = text.find('{')
    if json_start == -1:
        return None
    brace_count = 0
    for i in range(json_start, len(text)):
        if text[i] == '{':
            brace_count += 1
        elif text[i] == '}':
            brace_count -= 1
        if brace_count == 0:
            json_str = text[json_start:i+1]
            try:
                json_obj = json.loads(json_str)
                return json_obj
            except json.JSONDecodeError:
                return None
    return None


def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


class ChatBot:
    def __init__(self, api_key):
        self.api_key = api_key
        self.max_tokens = 400
        self.context = [ ]

    def add_message(self, role, message):
        self.context.append({
            "role": role,
            "content": message # {"type": "text", "text": message}
        })

    def ask(self, message):
        self.add_message("user", message)
        return self.call_openai()

    def set_system_prompt(self, message):
        self.add_message("system", message)

    def ask_image(self, prompt, image_path):
        image_encoded = encode_image(image_path)

        self.add_message("user", prompt)

        self.context.append({
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {
                    "url": f"data:image/jpeg;base64,{image_encoded}"
                }}
            ]
        })
        print("argh")
        return self.call_openai()

    def call_openai(self):
        payload = {
            "model": "gpt-4-vision-preview",
            "messages": self.context,
            "max_tokens": self.max_tokens
        }

        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            },
            json=payload
        )
        response_json = response.json()

        response = response_json.get('choices', [{}])[0].get('message', {}).get('content', '') 
        self.add_message("assistant", response)

        print(response)

        with open("gptctx.txt", "w") as file:
            file.write(str(self.context))

        return response

def main():
    api_key = os.getenv("OPENAI_API_KEY")
    chatbot = ChatBot(api_key)

    prompt = f'''
You'll pilot a Windows 11 computer. Output commands as:

Limit mouse usage; it might be imprecise. You must position the cursor directly over targets. Images received are at {LOWX}x{LOWY} resolution.

Examples:

{{
    "mouse": [
        {{
            "x_coordinate": 1, // You will get a chance to adjust your mouse coordinates to click the target.
            "y_coordinate": 1,
            "button_side": "left" || "right"
        }},
        {{
            "x_coordinate": 1,
            "y_coordinate": 1,
            "button_side": "left" || "right"
        }}
    ],
    "keyboard": [
        {{
            "special_keys": "ctrl+shift+space+enter",
            "words": "anything you put here will be typed"
        }},
        {{
            "words": "the fox jumped over the lazy dog"
        }}
    ]
}}

Exclude 'mouse' or 'keyboard' if unused.

No user queries; decide independently. State reasoning, then add commands.

Complete with:

{{
    {{
        "task_over": []
    }}
}}

TASK:  {input("Task for GPT-4: ")}
'''

    chatbot.set_system_prompt(prompt)
    start_screenshotting(chatbot)


def get_suffix(number): 
    remainder = number % 10 
    base = number - remainder

    if base == 10:
        return number + "th"

    tri = { 
        1: "st",
        2: "nd",
        3: "rd",
    }

    suffix = tri.get(remainder)
    snumber = str(number)
    
    if suffix:
        return snumber + suffix
    
    return snumber + "th" 
        

def plot_cursor(img, x, y):
    img = img.copy()
    mx = int(64/DOWNSCALE_FACTOR)
    my = int(64/DOWNSCALE_FACTOR)

    overlay = Image.open("cursor.png").resize((mx, my))

    img.paste(overlay, (x, y), overlay)  
    img.save("overlay.png")

    return "overlay.png"

def de_emojify(inputString):
    return inputString.encode('ascii', 'ignore').decode('ascii')

def handle_keyboard(keyboarddata):
    time.sleep(1)
    keys = keyboarddata.get('special_keys')
    words = keyboarddata.get('words')

    if words:
        keyboard.write(words, 0.1)



    if keys and not keys == "":
        keyboard.press(keys)
        time.sleep(1)
        keyboard.release(keys)


def handle_mouse(mousedata, chatbot, screenshot):
    x = mousedata.get('x_coordinate') 
    y = mousedata.get('y_coordinate') 

    button_type = mousedata.get('button_side')


    while True:
        print(x, y)
        confirmation_image = plot_cursor(screenshot, x, y)
        output = chatbot.ask_image('''Cursor is at previous X, Y on this image. To adjust the coordinates, reply with:
{
    "x_coordinate": x,
    "y_coordinate": y
}

To keep as is, reply with:

{
    "no_adjust": []
}

Use a code block for JSON responses.''', confirmation_image)

        output = output = remove_comments(output)
        output = extract_json(output) # will change to be more robust later

        
        if output.get('no_adjust') == []:
            break

        x = output['x_coordinate'] 
        y = output['y_coordinate'] 
        
    x = x * DOWNSCALE_FACTOR
    y = y * DOWNSCALE_FACTOR
    pyautogui.moveTo(x, y)
    pyautogui.click(button=button_type)




def start_screenshotting(chatbot):
    amount_of_screenshots = 1 
    while True:
        screenshot = pyautogui.screenshot()
        image_name = f"screen{amount_of_screenshots}.png"
        screenshot.save(image_name)
        
        img = Image.open(image_name)

        
        img = img.resize((LOWX, LOWY))
        img.save(image_name)

        output = chatbot.ask_image(f'{get_suffix(amount_of_screenshots)} screenshot of the computer', image_name)
        amount_of_screenshots += 1 

        output = output = remove_comments(output)
        output = extract_json(output) # will change to be more robust later
        if not output:
            continue
        mouse = output.get('mouse')
        keyboard = output.get('keyboard')

        if mouse:
            for mousedata in mouse:
                handle_mouse(mousedata, chatbot, img)


        if keyboard:
            for keyboarddata in keyboard:
                handle_keyboard(keyboarddata)

        if output.get('task_over') == []:
            print("Executed task successfully.")
            break

        time.sleep(5)
main()

