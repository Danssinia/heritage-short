# Ethics: consent, licences, labelling

> **Gate:** a real person shown or voiced without a consent record here scores the film zero.
> Record consent **before** generating any image or line of that person.

## Consent records

Each record: who, what they agreed to (likeness as an illustrated character, the exact words
put in their mouth, public posting), how (in person / voice note / message), when, and where
the evidence is kept (not in this repo if it is private).

### consent-dad
- **Person:** my father (shown as an illustrated character; his line in s08 is spoken by a Gemini TTS voice, not a clone of his voice)
- **Agreed to:** TODO (likeness, the s08 line "ተመልሼ የመጣሁት ይቅርታ ስላላችሁኝ ነው። የምበላው ለእናንተ ብዬ ብቻ ነው!", public posting on TODO platforms)
- **How / when:** TODO
- **Evidence kept at:** TODO

### consent-mom
- **Person:** my mother (illustrated character, no voice)
- **Agreed to:** TODO
- **How / when:** TODO
- **Evidence kept at:** TODO

### consent-me
- **Person:** me (illustrated character; narration by a Gemini TTS voice)
- **Agreed to:** yes (it is my own story)
- **Date:** TODO

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

Only the narration lines, prompts and generated images leave my machine. No surnames, addresses
or photos of my family are sent to any API.
