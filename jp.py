import asyncio
import os
import sys

from anki.collection import Collection
from anki.notes import Note
from dotenv import load_dotenv
from elevenlabs import save
from elevenlabs.client import AsyncElevenLabs
from openai import OpenAI

load_dotenv()

COL_PATH = "/home/bsag/.local/share/Anki2/bsag/collection.anki2"


def remove_dupes(col: Collection):
    query = '"deck:MvJ Kaishi" -card:0'
    card_ids = col.find_cards(query)
    col.remove_cards_and_orphaned_notes(card_ids)


def normalize_cards(col: Collection):
    query = '"deck:MvJ Kaishi"'
    note_ids = col.find_notes(query)
    for note_id in note_ids:
        note = col.get_note(note_id)
        note.fields = [val.replace("<br>", "") for val in note.fields]
        note.fields[0] = note.fields[0].lower()
        col.update_note(note)


def generate_sentence_and_explanation(col: Collection, note: Note):
    client = OpenAI()
    prompt = (
        "Dada uma palavra em japonês:\n\n"
        "1. Escreva uma frase de exemplo curta e simples em japonês que inclua claramente essa palavra exata.\n"
        "2. Forneça uma breve explicação em português de seu significado (não uma tradução direta). Evite repetir a palavra e não comece com frases como 'Significa...' ou 'Esta é uma palavra que descreve...', dê o significado diretamente. Se for um número, use outros números como referência, não o número em si. Não use nenhuma palavra em japonês, todas as palavras devem estar em português.\n"
        "3. Separe a frase e a explicação com um '$'. Não produza mais nada.\n\n"
        f"Palavra: {note["word"]}"
    )

    print("\tGenerating sentence and explanation...")
    response = client.responses.create(model="gpt-4.1", input=prompt)

    print(response.output_text)
    [sentence, explanation] = response.output_text.split("$")
    note["sentence"] = sentence
    note["explanation"] = explanation

    col.update_note(note)


async def generate_audios(col: Collection, note: Note):
    client = AsyncElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
    voice_id = "nPczCjzI2devNBz1zQrb"

    if not note["word_audio"].startswith("["):
        print("\tGenerating word audio...")
        result = client.text_to_speech.convert(
            model_id="eleven_turbo_v2_5",
            voice_id=voice_id,
            language_code="fr",
            text=note["word"],
        )
        audio_chunks = [chunk async for chunk in result]
        word_audio = b"".join(audio_chunks)
        save(
            word_audio,
            os.path.join(col.media.dir(), f"{note.id}_word.mp3"),
        )
        note["word_audio"] = f"[sound:{note.id}_word.mp3]"

    if not note["sentence_audio"]:
        print("\tGenerating sentence audio...")
        result = client.text_to_speech.convert(
            model_id="eleven_multilingual_v2",
            voice_id=voice_id,
            text=note["sentence"],
        )
        audio_chunks = [chunk async for chunk in result]
        sentence_audio = b"".join(audio_chunks)
        save(sentence_audio, os.path.join(col.media.dir(), f"{note.id}_sentence.mp3"))
        note["sentence_audio"] = f"[sound:{note.id}_sentence.mp3]"

    if not note["explanation_audio"]:
        print("\tGenerating explanation audio...")
        result = client.text_to_speech.convert(
            model_id="eleven_turbo_v2_5",
            voice_id=voice_id,
            language_code="en",
            text=note["explanation"],
        )
        audio_chunks = [chunk async for chunk in result]
        explanation_audio = b"".join(audio_chunks)
        save(
            explanation_audio,
            os.path.join(col.media.dir(), f"{note.id}_explanation.mp3"),
        )
        note["explanation_audio"] = f"[sound:{note.id}_explanation.mp3]"

    col.update_note(note)


async def fill_n_cards(col: Collection, n: int):
    note_ids = col.find_notes('"deck:MvJ Kaishi"')
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
