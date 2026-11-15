# Pinochle at The Family Table

The game shelf links to `/games/pinochle/`. Create a room and invite exactly three other human players. No bots or spectators are included. Rooms, chat, and sessions use the same Django service and SQLite storage as 31. No extra dependencies, services, or migrations are required.

## Default game

Four players with fixed partnerships across the table: seats 1 and 3 versus seats 2 and 4. Seats follow join order; have your partner join third if you host. A double deck contains 80 cards, with four copies of A, 10, K, Q, J in each suit. Each player receives 20. First dealer is seat 1, rotating each hand; bidding begins to the dealer's left. The bid winner leads the first trick.

Defaults use the double-deck partnership game described by [Pagat](https://www.pagat.com/marriage/pindd.html), with an explicit requirement to take a trick before counting meld. There is no universally accepted set of house rules. The setup page lists the complete implemented scoring table and explains the selected defaults. Meld is calculated automatically and only cards participating in meld are revealed. Partners do not combine cards across hands to create meld.

The table validates bids and plays on the server and highlights legal cards. Identical cards have distinct internal IDs, and ties go to the earliest played card. All four players confirm after seeing meld and after each completed trick; this keeps the table visible until everyone has reviewed it. The final trick proceeds directly to hand scoring. The last completed trick remains available during the next trick. The latest 20 hand scores are retained, including bids, meld, trick points, score changes, and totals.

## House rules

The creator can choose these before making a room:

- Winning score: 250, 500 (default), or 1000.
- Opening bid: 25 or 50 (default).
- Bidding partners pass no cards (default), 3, or 4 cards. Exchanges take place after trump is called, simultaneously and privately; neither sees incoming cards before committing their selection.
- Minimum team meld: none (default) or 20. If the bidding side misses the minimum, they are set without play; opponents score qualifying meld only.
- Minimum team trick points: none (default, but at least one trick is required) or 20.
- Require a trump marriage before passing: yes (default) or no. If required and the bidder has no marriage in any suit, they concede; the bid is deducted and opponents score zero.
- Bids above 60 must be multiples of five: yes (default) or no. Passing withdraws a player permanently from that auction. If the first three pass, the dealer takes the opening bid automatically.
- Must beat the winning card when possible: yes (default) or no. Following suit and trumping when void are always required; when enabled, beating applies even when your partner is winning.

Rules stay fixed for a room and its rematches, and every player can inspect them in the room sidebar. Create another room to change options. Single-deck play, other player counts, different meld tables, optional surrender when a trump marriage exists, and exchanging cards before choosing trump are not implemented. Meld tables and the engine are separate from 31 in `game/pinochle.py`, making future variants possible without changing 31's rules.

## Deployment and checks

Use the existing Render deployment. Push the source updates; the normal build collects the new static file. Restarting or deploying a free Render service clears temporary rooms, including long pinochle matches. Deploy between games. Refresh open browsers afterward. No database migration is needed for this feature.

```powershell
.\.venv\Scripts\python manage.py test
.\.venv\Scripts\python manage.py check
node --check static/pinochle.js
```

Tests cover meld overlap and multiplicity, the forced dealer bid, illegal bidding, trick obligations, duplicate-card ties, private exchanges, minimums, scoring, victory ties, ready barriers, rematches, and full hands through both the rules engine and four independent Django sessions. The existing 31 tests also run. The pinochle setup page has been inspected in the local browser; a full four-human browser game remains a useful acceptance check before family game night.
