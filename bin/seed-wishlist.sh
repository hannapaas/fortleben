#!/bin/sh
# Seed the public wishlist with a few works, so the page shows the idea. Run once on a new database:
#   sh bin/seed-wishlist.sh            (or KEIKAKU_DB=/path/to/keikaku.db sh bin/seed-wishlist.sh)
# Each line fetches the work from Aozora, checks its rights, and writes its summary.
set -e
db=${KEIKAKU_DB:+--db "$KEIKAKU_DB"}
w() { uv run keikaku $db wish "$1" --summary "$2" ${3:+--title "$3"}; }
w https://www.aozora.gr.jp/cards/000091/card50354.html "Momotarō told from the ogres' side. To avenge his raid, an ogre couple pray for a son of their own born from a bitter peach, and the giant they get sets off for Japan with a dragon, a baboon and a wolf; it does not go to plan." "The Ogres' Momotarō"
w https://www.aozora.gr.jp/cards/000038/card331.html "A man who loves stones above everything nets one from a river that breathes clouds before it rains. Thieves, officials and a strange old man all take it from him, and the stone keeps coming back: a retelling of an old Chinese tale." "Shi Qingxu"
w https://www.aozora.gr.jp/cards/000163/card47137.html "On her eleventh birthday a girl asks her mother what a 'golden opportunity' is, and decides they only come to heroes in books. Then she gives a single sen to a poor old woman and finds out what it was worth."
w https://www.aozora.gr.jp/cards/000221/card48111.html "A man with no work and no money drifts into Ueno Zoo on a summer afternoon and decides to spend the night hiding there. In the bamboo grass after dark he finds someone else hiding, with a pistol and a reason."
w https://www.aozora.gr.jp/cards/000077/card45249.html "A restless traveller bribes his way aboard an old pearling ship out of Morocco and is carried, through pirates and a storm, into an endless night at the bottom of the world. His account comes back in a bottle."
w https://www.aozora.gr.jp/cards/000254/card61120.html "A summer remembered on Mount Rokkō above Kobe: scabious in the grass, foreigners back from golf, the sea far below and the lights of the towns at night. A short essay with two of her own poems in it."
w https://www.aozora.gr.jp/cards/001351/card49202.html "A family story about an old calico cat who lived eighteen years in the narrator's great-grandmother's house, until one winter's day she stretched on the kotatsu and said, 'Ah, I'm tired.'"
