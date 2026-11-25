# Ethics: consent, licences, labelling

> **Gate:** a real person shown or voiced without a consent record here scores the film zero.
> Record consent **before** generating any image or line of that person.

## Consent records

Each record: who, what they agreed to (likeness as an illustrated character, the exact words
put in their mouth, public posting), how (in person / voice note / message), when, and where
the evidence is kept (not in this repo if it is private).

### consent-dad
- **Person:** my late father. He has passed away, so consent was given on his behalf by my mother, his wife and closest family member.
- **Shown as:** an illustrated character (not a photo or realistic likeness). His line in shot s08 is spoken by a prebuilt Gemini TTS voice ("Charon"), not a clone of his voice.
- **Agreed to (by my mother, on his behalf):** his depiction as an illustrated character; the words put in his mouth in s08, "ተመልሼ የመጣሁት ይቅርታ ስላላችሁኝ ነው። የምበላው ለእናንተ ብዬ ብቻ ነው!" ("I only came back because you said sorry. I'm only eating for you!"), which are the words he really said; and public posting of the film with an AI label.
- **How / when:** [in person], 25 November 2026, after I explained the story, the AI pictures and voices, and that the film will be public.
- **Evidence kept at:** a private voice note / message from my mother (not stored in this public repository).
- **Photo-based likeness:** a real photo is used once, privately, as the reference for the illustrated character (sent only to Cloudflare Workers AI; never published or committed). My mother agreed to this on 25 November 2026.

### consent-mom
- **Person:** my mother, shown as an illustrated character; she has no spoken lines.
- **Agreed to:** her depiction, the story as narrated, and public posting with an AI label.
- **How / when:** [in person], 25 November 2026.
- **Evidence kept at:** the same private voice note / message (not stored in this repository).
- **Photo-based likeness:** a real photo is used once, privately, as the reference for the illustrated character (sent only to Cloudflare Workers AI; never published or committed). My mother agreed to this on 25 November 2026.

### consent-me
- **Person:** me, the narrator, shown as an illustrated character; the narration is a prebuilt Gemini TTS voice, not my own voice.
- **Agreed to:** yes; it is my own story and my own decision to publish it.
- **Date:** 25 November 2026.
- **Photo-based likeness:** my own photo is used the same way, with my agreement.

No voice cloning is used: every voice is a prebuilt Gemini voice.

## Licences of every model and output

| Component | Licence / terms | Notes |
|---|---|---|
| Gemini 3.8 Flash TTS, Gemini text (Google) | Gemini API terms (free tier: Google may use inputs to improve products) | Private family details kept out of prompts; only the story lines are sent |
| FLUX.2 [klein] 4B (Black Forest Labs) on Cloudflare Workers AI | Apache 2.0 (4B); Cloudflare Workers AI terms | The 9B variant is non-commercial; not used |
| Wan 2.2 TI2V-5B (Alibaba Wan team) | Apache 2.0 | Run on Kaggle |
| ACE-Step 1.5 | MIT; outputs usable commercially | Run on Kaggle |
| FFmpeg | LGPL/GPL | Local tool, not a model |
| This repository's code | MIT | |

## Labelling plan

- The film ends with a 3-second end card: "Made with AI" plus how it was made.
- Posted with the platform's AI-content disclosure switched on (TikTok "AI-generated" / YouTube "altered or synthetic content" / Instagram "AI info").
- Generated files are not stripped of any watermark or provenance metadata.

## Style and identity

The look is described by qualities ("warm hand-painted storybook illustration, soft gouache texture"),
never by naming a living artist. Characters are illustrated, not photorealistic, so the film does
not create realistic deepfakes of my parents.

## Private data

Only the narration lines, prompts, generated images and, with my mother's consent, one private
photo per family member leave my machine. Each photo is sent once to Cloudflare Workers AI at the
reference stage, is kept in private/ (excluded from git) and is never published. No surnames or
addresses are sent to any API.
