## MOZTTS

#### What is it?

This extension for Oobabooga's Text Generation Web UI adds another method to 
generate Text To Speech files, this time using [Mozilla TTS](https://github.com/mozilla/TTS).

### Installation
clone this directory in the `extensions` directory. 
Enter your venv or conda environment and run `pip install -r requirements.txt` in the cloned directory moztts.
Either check the extension on the "Interface mode" tab or add this when starting
oobabooga : `--extension moztts`

That's it.

### Use
The UI works pretty much like the Silero_tts extension (very probably because I reused most of the code).

#### Additional options are

* **Use Cuda** : I won't even start to explain what it does.
* **Speaker** : this is empty for most voices, but some voice-models have multiple "speakers" in one file. You can choose 
 which to use here. Sadly I couldn't find a fast way to rebuild the gradio interface and fill or empty the speaker pull-down
 menu when needed, so if a voice needs a speaker index you will need to start a text generation by entering any text in the input box
 to save your settings, and then reload the page. The speaker pull-down menu will then be filled. I'm grateful for any hint on how to 
 automate this.

### Some important tidbits

* **Voice models will be downloaded when you first use them**, so be prepared to wait! Speed and quality
of the models is also very varied, so you might want to check the 
[descriptio of released models](https://github.com/mozilla/TTS/wiki/Released-Models) if your connection
isn't great. Once the model is loaded the TTS generation is usually quite fast (tortoise models non-withstanding)
* The settings are saved in the file `extensions/moztts/tts_config.json`. I included my favourite voice (at least
that I found so far ... there are really tons of them), but don't be afraid to try other out. 
Not everybody thinks "bored woman after a night of partying" is a great voice for a LLM.

#### Sample Voices
I added a script to generate samples of all english non-vocoder voices. You don't need to run it, as the samples are included in the directory `samples` (I'm sure you wouldn't have guessed). There is also a nifty libreoffice sheet with timing information on each voice called `timing.csv`. 