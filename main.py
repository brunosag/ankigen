import asyncio
import os
import sys

from anki.collection import Collection
from anki.notes import Note
from dotenv import load_dotenv
from openai import OpenAI
from google.cloud import texttospeech  # type: ignore

load_dotenv()

COL_PATH = "/home/bsag/.local/share/Anki2/bsag/collection.anki2"


def remove_dupes(col: Collection):
    query = '"deck:MvJ French" -card:0'
    card_ids = col.find_cards(query)
    col.remove_cards_and_orphaned_notes(card_ids)


def normalize_cards(col: Collection):
    query = '"deck:MvJ French"'
    note_ids = col.find_notes(query)
    for note_id in note_ids:
        note = col.get_note(note_id)
        note.fields = [val.replace("<br>", "") for val in note.fields]
        note.fields[0] = note.fields[0].lower()
        col.update_note(note)


def generate_sentence_and_explanation(col: Collection, note: Note):
    client = OpenAI()
    prompt = (
        "You are an assistant for beginner French learners.\n\n"
        "Given a French word:\n\n"
        "1. Write a short, simple French example sentence that clearly includes this exact word.\n"
        "2. Give a brief English explanation of its meaning (not a direct translation). Avoid repeating the word and do not start with phrases like 'It means...' or 'This is a word describing...', give the meaning straight away. If it's a number, use other numbers for reference, not the number itself. Don't use any French words, all words should be in English.\n"
        "3. Separate the sentence and explanation with a '$'. Output nothing else.\n\n"
        f"Word: {note["word"]}"
    )

    print("\tGenerating sentence and explanation...")
    response = client.responses.create(model="gpt-4.1", input=prompt)

    [sentence, explanation] = response.output_text.split("$")
    note["sentence"] = sentence
    note["explanation"] = explanation

    col.update_note(note)


async def generate_audios(col: Collection, note: Note):
    client = texttospeech.TextToSpeechClient()
    voice = texttospeech.VoiceSelectionParams(
        language_code="fr-FR",
        ssml_gender=texttospeech.SsmlVoiceGender.MALE,
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    )

    if not note["word_audio"].startswith("["):
        print("\tGenerating word audio...")
        synthesis_input = texttospeech.SynthesisInput(text=note["word"])
        response = client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )
        with open(os.path.join(col.media.dir(), f"{note.id}_word.mp3"), "wb") as f:
            f.write(response.audio_content)
        note["word_audio"] = f"[sound:{note.id}_word.mp3]"

    if not note["sentence_audio"]:
        print("\tGenerating sentence audio...")
        synthesis_input = texttospeech.SynthesisInput(text=note["sentence"])
        response = client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )
        with open(os.path.join(col.media.dir(), f"{note.id}_sentence.mp3"), "wb") as f:
            f.write(response.audio_content)
        note["sentence_audio"] = f"[sound:{note.id}_sentence.mp3]"

    if not note["explanation_audio"]:
        print("\tGenerating explanation audio...")
        voice = texttospeech.VoiceSelectionParams(
            language_code="en-US",
            ssml_gender=texttospeech.SsmlVoiceGender.FEMALE,
        )
        synthesis_input = texttospeech.SynthesisInput(text=note["explanation"])
        response = client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )
        with open(
            os.path.join(col.media.dir(), f"{note.id}_explanation.mp3"), "wb"
        ) as f:
            f.write(response.audio_content)
        note["explanation_audio"] = f"[sound:{note.id}_explanation.mp3]"

    col.update_note(note)


async def fill_n_cards(col: Collection, n: int):
    note_ids = col.find_notes('"deck:MvJ French"')
    count = 0

    for note_id in note_ids:
        note = col.get_note(note_id)
        generated = False
        if not (note["sentence"] and note["explanation"]):
            print(note_id)
            generate_sentence_and_explanation(col, note)
            generated = True
        if not (
            note["sentence_audio"]
            and note["explanation_audio"]
            and note["word_audio"].startswith("[")
        ):
            if not generated:
                print(note_id)
            await generate_audios(col, note)
            generated = True
        if generated:
            count += 1
        if count == n:
            break


async def main():
    n = int(sys.argv[1])
    col = Collection(COL_PATH)
    try:
        await fill_n_cards(col, n)
    finally:
        col.close()


if __name__ == "__main__":
    asyncio.run(main())
