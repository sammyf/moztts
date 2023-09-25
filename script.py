import time
from pathlib import Path

import gradio as gr
import torch
from modules import chat, shared, ui_chat
from modules.utils import gradio
import re
import subprocess
import json
import glob, os

from TTS.api import TTS
from TTS.utils.manage import ModelManager
from TTS.utils.synthesizer import Synthesizer

torch._C._jit_set_profiling_mode(False)

global tts_character_config
with open('extensions/moztts/tts_config.json') as f:
    ttsconfig = json.load(f)

with open('extensions/moztts/tts_character_config.json') as f:
    tts_character_config = json.load(f)


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

# load model manager
MODEL_PATH = './tts_model/best_model.pth.tar'
CONFIG_PATH = './tts_model/config.json'
path = "extensions/moztts/models.json"
manager = ModelManager(path, progress_bar=True)

tts_path = None
tts_config_path = None
speakers_file_path = None
language_ids_file_path = None
vocoder_path = None
vocoder_config_path = None
encoder_path = None
encoder_config_path = None
vc_path = None
vc_config_path = None
model_dir = None
model_path = None
config_path = None
model_item = None
synthesizer = None

current_params = params.copy()
global old_params
old_params = params.copy()

global lastCharacter
lastCharacter = "---"
last_voice = params["voice"]


# Used for making text xml compatible, needed for voice pitch and speed control
table = str.maketrans({
    "<": "&lt;",
    ">": "&gt;",
    "&": "&amp;",
    "'": "&apos;",
    '"': "&quot;",
})
def tts(sentence, outpath):
    global tts_path, tts_config_path, speakers_file_path, language_ids_file_path, vocoder_path, vocoder_config_path, encoder_path, encoder_config_path, vc_path, vc_config_path, model_dir, model_path, config_path,model_item, synthesizer
    if synthesizer is None:
        load_model(params['voice'])

    if tts_path is not None:
        wav = synthesizer.tts(
            sentence,
            params['speaker'],
            None,
            None,
            reference_wav=None,
            style_wav=None,
            style_text=None,
            reference_speaker_name=None,
        )
    synthesizer.save_wav(wav, outpath)

def load_model(model_name):
    global tts_path, tts_config_path, speakers_file_path, language_ids_file_path, vocoder_path, vocoder_config_path, encoder_path, encoder_config_path, vc_path, vc_config_path, model_dir, model_path, config_path,model_item, synthesizer
    model_path, config_path, model_item = manager.download_model(model_name)
    # tts model
    if model_item["model_type"] == "tts_models":
        tts_path = model_path
        tts_config_path = config_path
        if "default_vocoder" in model_item:
            vocoder_name = model_item["default_vocoder"]

    # voice conversion model
    if model_item["model_type"] == "voice_conversion_models":
        vc_path = model_path
        vc_config_path = config_path

    # tts model with multiple files to be loaded from the directory path
    if model_item.get("author", None) == "fairseq" or isinstance(model_item["model_url"], list):
        model_dir = model_path
        tts_path = None
        tts_config_path = None
        vocoder_name = None

    # load models
    synthesizer =  Synthesizer(
        tts_path,
        tts_config_path,
        speakers_file_path,
        language_ids_file_path,
        vocoder_path,
        vocoder_config_path,
        encoder_path,
        encoder_config_path,
        vc_path,
        vc_config_path,
        model_dir,
        "voices",
        params['use_cuda'],
    )

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
        if (len(parts[0]) < 2) or ("vocoder" in parts[0][1]):
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

def remove_tts_from_history(history):
    for i, entry in enumerate(history['internal']):
        history['visible'][i] = [history['visible'][i][0], entry[1]]

    return history

def toggle_text_in_history(history):
    for i, entry in enumerate(history['visible']):
        visible_reply = entry[1]
        if visible_reply.startswith('<audio'):
            if params['show_text']:
                reply = history['internal'][i][1]
                history['visible'][i] = [history['visible'][i][0], f"{visible_reply.split('</audio>')[0]}</audio>\n\n{reply}"]
            else:
                history['visible'][i] = [history['visible'][i][0], f"{visible_reply.split('</audio>')[0]}</audio>"]

    return history


def state_modifier(state):
    if not params['activate']:
        return state

    state['stream'] = False
    return state

def clear_output_dir():
    # Specify the directory you want to delete files from
    dir_path = 'extensions/moztts/outputs/'

    # Use glob to match all files in the directory
    files = glob.glob(f'{dir_path}/*')

    # Loop over the list of filepaths & remove each file.
    for file in files:
        if os.path.isfile(file):
            os.remove(file)

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

def fixHash27(s):
    s=s.replace("&#x27;","'");
    return s

def output_modifier(string, state):
    global current_params, streaming_state, ttsconfig, lastCharacter, last_voice

    string = fixHash27(string)
    if not params['activate']:
        return string

    ## use the preset character voice, if the character was changed and we have a preset for it.
    if lastCharacter != state["character_menu"]:
        lastCharacter = state["character_menu"]
        if state["character_menu"] in tts_character_config:
            params["voice"] = tts_character_config[state["character_menu"]]["voice"]
            params["speaker"] = tts_character_config[state["character_menu"]]["speaker"]

    if last_voice != params["voice"]:
        load_model(params["voice"])
        last_voice = params["voice"]

    original_string = string

    if string == '':
        string = '*Empty reply, try regenerating*'
    else:
        output_file = Path(f'extensions/moztts/outputs/{state["character_menu"]}_{int(time.time())}.wav')
        tts(string, output_file)
        # voice_string = f'--model_name={params["voice"]}'
        # if "vocoder" in params['voice']:
        #     voice_string = f'--vocoder_name={params["voice"]}'
        # command = ["tts",f'--text="{string}"', f"{voice_string}","--emotion=true",f'--use_cuda={params["use_cuda"]}' ,f'--out_path={output_file}']
        # if params["speaker"] != "":
        #     speaker_string = f"--speaker_idx={params['speaker']}"
        #     command.append(speaker_string)
        # subprocess.run(command, capture_output=True, text=True)

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
        with gr.Row():
            clear = gr.Button('Permanently delete generated audios files from your drive')
            clear_cancel = gr.Button('Cancel', visible=False)
            clear_confirm = gr.Button('Confirm (cannot be undone)', variant="stop", visible=False)

        gr.Markdown('you need to write something to the LLM and then reload the page if the selected voices needs a speaker idx.')


    convert_arr = [convert_confirm, convert, convert_cancel]
    convert.click(lambda: [gr.update(visible=True), gr.update(visible=False), gr.update(visible=True)], None, convert_arr)
    convert_confirm.click(
        lambda: [gr.update(visible=False), gr.update(visible=True), gr.update(visible=False)], None, convert_arr).then(
        remove_tts_from_history, gradio('history'), gradio('history')).then(
        chat.save_history, gradio('history', 'unique_id', 'character_menu', 'mode'), None).then(
        chat.redraw_html, gradio(ui_chat.reload_arr), gradio('display'))

    convert_cancel.click(lambda: [gr.update(visible=False), gr.update(visible=True), gr.update(visible=False)], None, convert_arr)

    # Clear outputs with confirmation
    clear_arr = [clear_confirm, clear, clear_cancel]
    clear.click(lambda: [gr.update(visible=True), gr.update(visible=False), gr.update(visible=True)], None,
                clear_arr)
    clear_confirm.click(
        lambda: [gr.update(visible=False), gr.update(visible=True), gr.update(visible=False)], None, convert_arr).then(
        clear_output_dir, None, None).then(
        chat.save_history, gradio('history', 'unique_id', 'character_menu', 'mode'), None).then(
        chat.redraw_html, gradio(ui_chat.reload_arr), gradio('display'))
    clear_cancel.click(lambda: [gr.update(visible=False), gr.update(visible=True), gr.update(visible=False)], None, clear_arr)

    # Toggle message text in history
    show_text.change(
        lambda x: params.update({"show_text": x}), show_text, None).then(
        toggle_text_in_history, gradio('history'), gradio('history')).then(
        chat.save_history, gradio('history', 'unique_id', 'character_menu', 'mode'), None).then(
        chat.redraw_html, gradio(ui_chat.reload_arr), gradio('display'))

    # Event functions to update the parameters in the backend
    activate.change(lambda x: params.update({"activate": x}), activate, None)
    autoplay.change(lambda x: params.update({"autoplay": x}), autoplay, None)
    use_cuda.change(lambda x: params.update({"use_cuda": x}), use_cuda, None)
    voice.change(lambda x: params.update({"voice": x}), voice, None).then(chat.redraw_html, gradio(ui_chat.reload_arr), gradio('display'));
    speaker.change(lambda x: params.update({"speaker": x}), speaker, None)


