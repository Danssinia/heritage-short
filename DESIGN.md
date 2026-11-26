# Design

> Fill in every `TODO` with what really happened. Graders read this file as evidence;
> write what people actually said, in their words, and what you changed because of it.

## Audience and intent (written before generating anything)

- **Who watches:** my family and relatives in Ethiopia and abroad. TODO: name the groups
  concretely, e.g. "my parents, my cousins in Addis and in the diaspora, my friends on TikTok".
- **Where:** on their phones, in the family group chat and on my social media, so the
  **vertical** version is the main one, with sound often on low.
- **What they should feel or understand at the end:** they laugh at a moment they recognise,
  remember our father with love, and leave feeling that in our family a simple "sorry" is enough to
  bring someone back to the table.
- **How might we:** how might we turn a two-minute family joke into something relatives far away
  can share and laugh at together?

## The story

Logline: one breakfast, my mother and I tease my father until he leaves the table; a smile and a
"sorry" bring him back, with a line our family still laughs about.

Beats: together at breakfast → teasing → Dad is not laughing → he leaves → washes his hands →
returns and stands quietly → we smile and apologise → he laughs, sits down: "I'm only eating
for you!" → today we still laugh about it.

Every shot's reason is in `storyboard.json` (`shots[].reason`).

TODO (honesty note): mark which details are exactly as they happened and which you added for
the film (for example, the closing line in s09 and the food on the table).

## User test 1: radio cut (narration + placeholder music on black)

Date: 25 November 2026 (evening) · Format: WhatsApp · File: `outputs/final/radio_cut.mp4`

| Person | What they said (their words) | Where they reacted |
|---|---|---|
| Brother 1 | "Honestly, I really love the story and the creativity behind this project. The video generation is impressive, but what amazed me most is the audio — it sounds so natural and human-like, almost as if a real person is speaking. You're doing something really amazing. Keep pushing, this has great potential!" | the narration voice |
| Brother 2 | Asked: What happened in the story? Which part made you laugh? Did you notice any incorrect Amharic words? Answer: "A son and his mom made dad angry by joking about things he dont like while he was eating his bf.. Then he gets angry… I am only eating for you😁 No incorrect word" | Dad's line in s08 |
| Mom | She loved it and remembered it as if it had happened yesterday; she often shares the story with other family members. (paraphrased from her spoken reply) | the whole story |

**What I changed because of it:**

1. Testers retold the story correctly, laughed at Dad's line and found no incorrect Amharic, so the narration lines and voices stay as they are (evidence that the Amharic script and the Puck/Charon voices work).

## User test 2: near-final cut

Date: 26 November 2026 · Version tested: the first full build (commit c55c0fa) · File: `outputs/final/heritage_vertical_9x16.mp4`

| Person | What they said (their words) | Where they reacted |
|---|---|---|
| Brother 1 | "What if we added a heartfelt note at the end, such as “In loving memory of our dad”? It could make Mom happy and give the piece a more personal, meaningful touch." | the end card |
| TODO | TODO | TODO |
| TODO | TODO | TODO |

**What changed because of it:**

1. Following my brother's suggestion (our father has passed away), the end card now dedicates the film to him: "In loving memory of our dad, Abbaye." This also fits my mother's feedback in test 1 that she often shares this story with the family.

## Questions to ask testers (keep them open)

- What happened in the story, in your own words?
- Which moment did you like most? Where did you lose interest?
- Was any Amharic word or name pronounced wrongly?
- Could you read the subtitles on your phone?
- Is anything about our family wrong or something you would not want shared?
