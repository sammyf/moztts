import subprocess
import re

TEST_STRING="In this bustling world of endless possibilities, where creativity flows like a river, " \
            "let's explore the vast expanse of language and communication, unlocking the secrets of the universe's" \
            " hidden meanings and expressions, let's begin our adventure with a cheerful and energetic voice, " \
            "eager to assist you in finding information, answering any query with aplomb."

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

def generate_sample(string, model, speaker):
    if string == '':
        string = '*Empty reply, try regenerating*'
    else:
        output_file = f'samples/{model.replace("/","__")}__{speaker}.wav'
        print("output: "+output_file)
        voice_string = f'--model_name={model}'
        if "vocoder" in model:
            voice_string = f'--vocoder_name={model}'
        command = ["tts",f'--text="{string}"', f"{voice_string}","--emotion=true",f'--use_cuda=true' ,f'--out_path={output_file}']
        if speaker != "(single_speaker)":
            speaker_string = f"--speaker_idx={speaker}"
            command.append(speaker_string)
        result = subprocess.run(command, capture_output=True, text=True)
        with open('samples/timing.csv', 'a') as f:
            pattern = r".*Processing time: ([\d\.]+)\n"
            match = re.findall(pattern, result.stdout.strip())
            f.writelines(f"{model};{speaker};{match[0]};{output_file}\n")
    return

print("Welcome to the moztts sample generation.\n")
print("Be aware that this is going to take a long time\n")
print("Grabbing model list ...")
with open('samples/timing.csv', 'w') as f:
    f.writelines("Voice;Speaker;Processing time;Filename\n\n")
models = load_model_list()
print(str(len(models))+" models loaded.")
m=1
for model in models:
    if "/en/" not in model or "/vocoder/" in model:
        continue
    s=1
    speakers = load_speaker_list(model)
    if len(speakers) == 0:
        print(f"Model {str(m)} : {model} has only a single speaker.\n Generating sample ...")
        try:
            generate_sample(TEST_STRING, model, "(single_speaker)")
        except:
            print("error on that model\nIgnoring ...")
        print("Done\n")
    else:
        print(f"Model {str(m)} : {model} has { str(len(speakers))} speakers.\n iterating ...")
        for speaker in speakers:
            print(f"Generating sample for speaker {str(s)} : {speaker} ...")
            try:
                generate_sample(TEST_STRING, model, speaker)
            except:
                print("error on that speaker\nIgnoring ...")
                continue
            print("Done.")
            s = s + 1
    m = m + 1
print("Samples were all generated.\n")