import time
from pathlib import Path

import gradio as gr
import torch
from modules import chat, shared
import re
import subprocess
import json

torch._C._jit_set_profiling_mode(False)

with open('extensions/moztts/tts_config.json') as f:
    ttsconfig = json.load(f)


params = {
    'activate': ttsconfig['activate'],
    'voice': ttsconfig['voice'],
    'speaker': ttsconfig['speaker'],
    'language': ttsconfig['language'],
    'show_text': ttsconfig['show_text'],
    'autoplay': ttsconfig['autoplay'],
    'use_cuda': ttsconfig['use_cuda'],
    'local_cache_path': ttsconfig['local_cache_path']
}

current_params = params.copy()
global old_params
old_params = params.copy()

# Used for making text xml compatible, needed for voice pitch and speed control
table = str.maketrans({
    "<": "&lt;",
    ">": "&gt;",
    "&": "&amp;",
    "'": "&apos;",
    '"': "&quot;",
})

def xmlesc(txt):
    return txt.translate(table)

def sort_voices(s):
    parts = s.split('/')
    return (parts[0], parts[1], parts[2],parts[3])

def load_model_list():
    model_list = []
    command = ["tts", "--list_models"]
    result = subprocess.run(command, capture_output=True, text=True)
    pattern = r"\n\s*(\d+:\s.+)"
    matches = re.findall(pattern, result.stdout.strip())

    for match in matches:
        pattern = r"(\d+):\s(.+)"
        parts = re.findall(pattern, match)
        if len(parts[0]) < 2:
            continue
        asterisk = ""
        fname = parts[0][1]
        if " [already downloaded]" in parts[0][1]:
             asterisk = "*"
             fname = parts[0][1].replace(" [already downloaded]", "")
        model_list.append(fname)
    # Sort the array using the custom sort key
    sorted_arr = sorted(model_list, key=sort_voices)

    return sorted_arr

def load_speaker_list( model):
    speaker_list = []
    command = ["tts", f"--model_name={model}","--list_speaker_idxs"]
    result = subprocess.run(command, capture_output=True, text=True)
    pattern = r"\n.*\{(.*)\}"
    arr_raw = re.findall(pattern, result.stdout.strip())
    arr = ""
    if len(arr_raw) > 0:
        arr = arr_raw[0]
    pattern = r"('.*?': \d+)"
    matches = re.findall(pattern, arr)

    for match in matches:
        spkr = match.split(':')
        spkr[0] = spkr[0].replace("'","")
        speaker_list.append(spkr[0])
    return speaker_list

def remove_tts_from_history():
    for i, entry in enumerate(shared.history['internal']):
        shared.history['visible'][i] = [shared.history['visible'][i][0], entry[1]]


def toggle_text_in_history():
    for i, entry in enumerate(shared.history['visible']):
        visible_reply = entry[1]
        if visible_reply.startswith('<audio'):
            if params['show_text']:
                reply = shared.history['internal'][i][1]
                shared.history['visible'][i] = [shared.history['visible'][i][0], f"{visible_reply.split('</audio>')[0]}</audio>\n\n{reply}"]
            else:
                shared.history['visible'][i] = [shared.history['visible'][i][0], f"{visible_reply.split('</audio>')[0]}</audio>"]


def state_modifier(state):
    if not params['activate']:
        return state

    state['stream'] = False
    return state


def input_modifier(string):
    global old_params, current_params
    # save changes back to json. Sadly Gradio can't just send events when something changed, so : every time.
    if( old_params != params):
        with open('extensions/moztts/tts_config.json', 'w') as f:
            json.dump(params, f, indent=4)
            current_params = params.copy()
            old_params = params.copy()

    if not params['activate']:
        return string

    shared.processing_message = "*Is recording a voice message...*"
    return string


def history_modifier(history):
    # Remove autoplay from the last reply
    if len(history['internal']) > 0:
        history['visible'][-1] = [
            history['visible'][-1][0],
            history['visible'][-1][1].replace('controls autoplay>', 'controls>')
        ]

    return history


def output_modifier(string):
    global current_params, streaming_state

    print( params)
    if not params['activate']:
        return string

    original_string = string

    if string == '':
        string = '*Empty reply, try regenerating*'
    else:
        output_file = Path(f'extensions/moztts/outputs/{shared.character}_{int(time.time())}.wav')
        voice_string = f'--model_name={params["voice"]}'
        if "vocoder" in params['voice']:
            voice_string = f'--vocoder_name={params["voice"]}'
        command = ["tts",f'--text="{string}"', f"{voice_string}","--emotion=true",f'--use_cuda={params["use_cuda"]}' ,f'--out_path={output_file}']
        if params["speaker"] != "":
            speaker_string = f"--speaker_idx={params['speaker']}"
            command.append(speaker_string)
        print("\ncommand: "+" ".join(command)+"\n")
        subprocess.run(command, capture_output=False, text=True)

        autoplay = 'autoplay' if params['autoplay'] else ''
        string = f'<audio src="file/{output_file.as_posix()}" controls {autoplay}></audio>'
        if params['show_text']:
            string += f'\n\n{original_string}'

    shared.processing_message = "*Is typing...*"
    return string


def setup():
    pass

def ui():
    model_list = load_model_list()
    speaker_list = load_speaker_list(params['voice'])
    print( speaker_list)

    # Gradio elements
    with gr.Accordion("Mozilla TTS"):
        with gr.Row():
            activate = gr.Checkbox(value=params['activate'], label='Activate TTS')
            autoplay = gr.Checkbox(value=params['autoplay'], label='Play TTS automatically')

        with gr.Row():
            use_cuda = gr.Checkbox(value=params['use_cuda'], label='Use CUDA')
            show_text = gr.Checkbox(value=params['show_text'], label='Show message text under audio player')
        voice = gr.Dropdown(value=params['voice'], choices=model_list, label='TTS voice')
        speaker = gr.Dropdown(value=params['speaker'], choices=speaker_list, label='TTS speaker for multi-speaker voices')
        with gr.Row():
            convert = gr.Button('Permanently replace audios with the message texts')
            convert_cancel = gr.Button('Cancel', visible=False)
            convert_confirm = gr.Button('Confirm (cannot be undone)', variant="stop", visible=False)
        gr.Markdown('you need to write something to the LLM and then reload the page if the selected voices needs a speaker idx.')
    # Convert history with confirmation
    convert_arr = [convert_confirm, convert, convert_cancel]
    convert.click(lambda: [gr.update(visible=True), gr.update(visible=False), gr.update(visible=True)], None, convert_arr)
    convert_confirm.click(
        lambda: [gr.update(visible=False), gr.update(visible=True), gr.update(visible=False)], None, convert_arr).then(
        remove_tts_from_history, None, None).then(
        chat.save_history, shared.gradio['mode'], None, show_progress=False).then(
        chat.redraw_html, shared.reload_inputs, shared.gradio['display'])

    convert_cancel.click(lambda: [gr.update(visible=False), gr.update(visible=True), gr.update(visible=False)], None, convert_arr)

    # Toggle message text in history
    show_text.change(
        lambda x: params.update({"show_text": x}), show_text, None).then(
        toggle_text_in_history, None, None).then(
        chat.save_history, shared.gradio['mode'], None, show_progress=False).then(
        chat.redraw_html, shared.reload_inputs, shared.gradio['display'])

    # Event functions to update the parameters in the backend
    activate.change(lambda x: params.update({"activate": x}), activate, None)
    autoplay.change(lambda x: params.update({"autoplay": x}), autoplay, None)
    use_cuda.change(lambda x: params.update({"use_cuda": x}), use_cuda, None)
    voice.change(lambda x: params.update({"voice": x}), voice, None)
    speaker.change(lambda x: params.update({"speaker": x}), speaker, None)


