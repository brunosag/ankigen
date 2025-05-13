import os

from dotenv import load_dotenv
from elevenlabs import play, save
from elevenlabs.client import ElevenLabs
from openai import OpenAI

from anki.collection import Collection
from anki.notes import Note

load_dotenv()

COL_PATH = "/home/bsag/.local/share/Anki2/bsag/collection.anki2"


def remove_dupes(col: Collection):
    query = "deck:essential_french -card:0"
    card_ids = col.find_cards(query)
    col.remove_cards_and_orphaned_notes(card_ids)


def normalize_cards(col: Collection):
    query = "deck:essential_french"
    note_ids = col.find_notes(query)
    for note_id in note_ids:
        note = col.get_note(note_id)
        note.fields = [val.replace("<br>", "") for val in note.fields]
        note.fields[0] = note.fields[0].lower()
        col.update_note(note)


def generate_sentence_and_explanation(col: Collection, note: Note):
    word = note["word"]

    client = OpenAI()
    prompt = (
        "You are an assistant for beginner French learners.\n\n"
        "Given a French word:\n\n"
        "1. Provide a short, simple French example sentence using it.\n"
        "2. Provide a brief English explanation of the word's core meaning (no direct translation). Avoid repeating the word itself and skip introductions like 'The word means...'.\n"
        "3. Separate the sentence and explanation with a '$'. Output nothing else.\n\n"
        f"Word: {word}"
    )
    print(f"Generating sentence and explanation for '{word}'...")
    response = client.responses.create(model="gpt-4.1", input=prompt)
    print("Done.")

    [sentence, explanation] = response.output_text.split("$")
    note["sentence"] = sentence
    note["explanation"] = explanation

    col.update_note(note)


def generate_audios(col: Collection, note: Note):
    sentence = note["sentence"]
    explanation = note["explanation"]

    client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
    voice_id = "ohItIVrXTBI80RrUECOD"

    print(f"Generating sentence audio for '{note["word"]}'...")
    sentence_audio = client.text_to_speech.convert(
        text=sentence,
        voice_id=voice_id,
    )
    print("Done.")
    print(f"Generating explanation audio for '{note["word"]}'...")
    explanation_audio = client.text_to_speech.convert(
        text=explanation,
        voice_id=voice_id,
    )
    print("Done.")

    sentence_audio_filename = "sentence_audio.mp3"
    explanation_audio_filename = "explanation_audio.mp3"

    save(sentence_audio, os.path.join(col.media.dir(), f"{note.id}_sentence.mp3"))
    save(explanation_audio, os.path.join(col.media.dir(), f"{note.id}_explanation.mp3"))

    note["sentence_audio"] = f"[sound:{note.id}_sentence.mp3]"
    note["explanation_audio"] = f"[sound:{note.id}_explanation.mp3]"

    col.update_note(note)


def fill_n_cards(col: Collection, n: int):
    note_ids = col.find_notes("deck:essential_french")
    count = 0
    for note_id in note_ids:
        note = col.get_note(note_id)
        generated = False
        if not note["sentence"] or not note["explanation"]:
            generate_sentence_and_explanation(col, note)
            generated = True
        if not note["sentence_audio"] or not note["explanation_audio"]:
            generate_audios(col, note)
            generated = True
        if generated:
            count += 1
        if count == 10:
            break


col = Collection(COL_PATH)

fill_n_cards(col, 10)

col.close()
