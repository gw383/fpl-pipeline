# Player rating methodology

Every player's rating comes from a **projection model** that predicts how many FPL points he will score in each of the next five gameweeks. The model lives in [`projections/model.py`](../projections/model.py), runs after `dbt build` (`python projections/run.py`), and writes three tables:

| Table | Grain | What's in it |
|---|---|---|
| `analytics.player_projection` | player × upcoming fixture | expected minutes, open-play xG, xA, expected penalties, clean-sheet chance and expected points by category |
| `analytics.player_rating` | player | expected points next gameweek and over the horizon, split by category; the 0–10 star rating |
| `analytics.team_rating` | team | attack, defence and defensive-actions-allowed multipliers |

## From a score to a prediction

An earlier version combined four 0–10 scores (quality, team strength, fixtures, defensive actions) with hand-picked weights. That produced a sensible-looking ranking. But its output was a score, not a quantity: nothing in the real world corresponds to "7.2", so there was no way to check it or to learn whether the weights were right.

This model predicts a number that is later observed: **FPL points in a specific fixture**. That changes three things:

1. **It can be tested.** After every gameweek, predicted and actual points can be compared (see [Backtest](#backtest)). Settings can then be tuned against real outcomes instead of guessed.
2. **Parts combine in the right way.** Minutes multiply everything, doubles add a second fixture, and a blank adds nothing. These fall out of the arithmetic instead of needing special rules.
3. **It's comparable across positions.** A 5-point defender and a 5-point forward are equally good picks, which a within-position score can't say.

## How a fixture's expected points are built

```
expected points = appearance + goals + assists + penalties + clean sheet
                + goals conceded + saves + defensive contribution + bonus + cards
```

Three sub-models feed every term, and penalties are handled separately (see [Penalties](#4-penalties)).

### 1. Team ratings

Each team gets an **attack** and a **defence** multiplier (1.0 = league average), fitted so that for every past match:

```
xG for ≈ league average × attack[team] × defence[opponent] × venue
```

- **Fitting method:** iterative proportional fitting. Each team's rating is adjusted for who it has played, so a side that has faced the top three isn't marked down for it.
- **Venue:** the home side's xG × 1.12 and the away side's ÷ 1.12 (`home_advantage`).
- **Recency:** matches are weighted by recency (`team_decay = 0.93` per gameweek).
- **Shrinkage:** each team gets `team_prior_matches = 4` matches of prior performance added. Five early-season games therefore can't make a side look like the best or worst in the league. Because older matches are weighted down, a team's own results make up at most about 78% of its rating, even late in the season.
- **What the prior is:** not plain average, but what the squad's **start-of-season prices** say (see [Prices as a prior](#prices-as-a-prior)). The attack prior is the average price of the team's six most expensive midfielders and forwards relative to the league's; the defence prior is the same for its five most expensive goalkeepers and defenders, inverted (an expensive defence is expected to concede less).

### 2. Player rates

For every player, recency-weighted (`form_decay = 0.90`) per-90 rates of xG, xA, defensive actions, saves, **base BPS** (see [Bonus](#5-bonus)) and yellow cards:

- **Opponent adjustment.** xG and xA are divided by how leaky that gameweek's opponent was at that venue. Saves are divided by how dangerous the opponent's attack was. Defensive actions are divided by how many that opponent gives away (below). A hat-trick of chances against the worst defence counts for less.
- **Defensive actions allowed.** Some teams make their opponents defend more than others. Each team gets a multiplier for how many defensive actions opposing defenders and midfielders make against it, fitted the same way as the team ratings (so it allows for who each side has played) and shrunk towards 1.0 by `defcon_prior_matches = 4` matches of average. After five gameweeks they range from about 0.93 (Brighton) to 1.11 (Brentford). City and Arsenal are close to average. Home and away sides make about the same number, so there's no venue term.
- **Shrinkage.** Each rate is blended with a prior using a small number of 90s' worth of it (`rate_prior_90s`: 2 for xG and xA, 1 for defensive actions). A substitute with one lucky 20-minute cameo can't top the table, while a regular's own numbers dominate quickly. For defensive actions, saves and cards the prior is the position average. For xG, xA and base BPS it is the position average × his start-of-season price ÷ the position's average price, so a £12m midfielder is pulled towards what a £12m midfielder usually produces, not towards a squad player's output.

#### Prices as a prior

FPL sets prices before the season from everything known about players and teams: previous seasons, transfers, role. Five games of this season can't match that, so the model uses **start-of-season prices** (current price − `cost_change_start`, so nothing learned from this season's games leaks in) as the prior for player xG, xA and base BPS (`price_prior_power = 1`) and for team attack and defence (`team_price_prior_power = 1`).

This fixed a systematic problem. Without it, the model shrank everyone towards the average, so the best players were under-predicted: in the gameweek 2–5 backtest, the most expensive 10% in each position scored about 1 point per game more than predicted, while everyone else was predicted almost exactly. With the price priors that gap falls from about 1.0 to 0.6 points per game, and every backtest measure improves (see [Backtest](#backtest)). A power of 1.5 scored slightly better overall, but it gave Haaland a prior of about 2 open-play xG per 90, far more than any striker sustains. At a power of 1 his prior is about 1.2, and the most expensive forwards are predicted almost exactly (0.1 points per game too low). The gap that's left is mostly goalkeepers and defenders of the top teams, whose clean sheets are still under-predicted.

#### Previous seasons as a prior

Once a season, the pipeline loads every player's previous Premier League seasons from FPL's `element-summary` history ([`player_past_seasons`](../transformation/models/analytics/player_past_seasons.sql)). Where a player has enough Premier League minutes, his own past rates are a much more direct guide than his price.

- **What's used:** per-90 open-play xG, xA, base BPS, defensive actions, saves and yellow cards from last season (`history_season_weights`). Adding the season before at half weight was tested and did slightly worse (see [Backtest](#backtest)).
  - **Penalties** are taken out of past xG the same way as this season's. Penalty goals come from the previous seasons' Premier League goal events, which are also loaded once.
  - **Defensive actions** are counted the way his *current* position counts them: defenders count clearances, blocks, interceptions and tackles; midfielders and forwards also count recoveries.
- **How much it's trusted:** trust = past 90s ÷ (past 90s + 15) (`history_confidence_90s`), so a full season of 30 games is trusted about two-thirds. The prior becomes trust × his past rate + (1 − trust) × the price-based prior. Players new to the league have no history and keep the price prior.
- **How much weight it gets:** the prior counts as up to `history_prior_90s = 8` extra 90s × trust. That fades by 5% per gameweek played this season (`history_fade = 0.95`), because last season gets less relevant as this one builds up.
- **Summer signings** (joined their club within about four months before the first deadline) have their past 90s counted at half (`history_mover_weight`). `history_past` doesn't say which club the numbers came from, and output at one club doesn't fully carry over to another.

**Breakouts.** A player who was poor last season and is flying now is pulled back towards last season early on, and this season's numbers take over as they build. For a regular starter with a full previous season, his own games this season make up about:

| Point in the season | Share of his xG rate from this season |
|---|---|
| Gameweek 6 | ~40% |
| Gameweek 12 | ~55% |
| Gameweek 20 | ~65% |
| Gameweek 30 | ~75% |

That's deliberate: most five-game hot streaks don't last, but a genuine breakout wins through within a couple of months. The settings above are starting values. Run `python projections/backtest.py --compare-priors` once the history is loaded to compare them with weaker and stronger versions (and with no history at all), then tune `ModelConfig`.

### 3. Minutes and availability

From the player's team's recent matches since he arrived (steeply weighted, `minutes_decay = 0.60`, so the last game matters most). A player added to FPL mid-season is judged from his debut, so weeks spent registering or getting fit as a new signing don't count as being dropped:

- the chance he **starts**, capped at 95% because even ever-presents get rested or injured;
- the chance of a **substitute appearance**;
- his typical minutes when starting or coming on, and the chance a start lasts **60+ minutes**.

FPL's availability flags scale these:

| Status | Effect |
|---|---|
| Left the club or ineligible (u, n) | 0 for every fixture |
| Flagged (d, i, s), next gameweek | FPL's chance-of-playing % (no % given = 50%) |
| Flagged, later gameweeks | 0 until a return date in the news ("Expected back 18 Oct", "Suspended until 4 Nov"); with no date, the gap closes by half each gameweek |

### 4. Penalties

Penalties are valuable to whoever takes them, but taking one says nothing about how well a player creates chances. FPL's xG counts every penalty as about 0.79 xG. Two penalties in five games can therefore make a midfielder look like an elite attacker: this season, Le Fée's xG per 90 was 0.37 including his two penalties and 0.06 without them. So the model treats penalties as a **role**, not as chance creation.

1. **Take penalties out of the history.** Penalties taken per player per gameweek come from [`player_penalties`](../transformation/models/analytics/player_penalties.sql). Scored penalties come from the Premier League's own match API, whose goal events are typed "Goal" / "Penalty" / "Own"; missed ones come from FPL. For each penalty, 0.79 xG is removed from that player-gameweek before anything is learned from xG. The team ratings and player rates above are therefore **open play only**.
2. **Project penalties forward as a role.**
   - **Team penalties:** each fixture's expected penalties for a team are the league penalty rate × the team's attack × the fixture's attacking context. Better attacks in easier fixtures win more.
   - **League rate:** the rate is this season's penalties per team per match, shrunk towards the long-run Premier League rate of about 0.14 by 100 matches' worth of it.
   - **Who takes them:** they go to the takers in FPL's penalty order. The first-choice taker takes one if he's on the pitch (expected minutes ÷ 90); otherwise it falls to the second choice, and so on.
   - **Points:** each expected penalty is worth 78% × the position's goal points, minus 22% × 2 for a miss.
3. **Put the penalty threat back for defences.** The opponent's expected penalty xG is added to expected goals conceded, so clean-sheet chances still account for penalties.

The result: a player who happened to take penalties recently but isn't the designated taker loses that boost. A new first-choice taker gets the boost straight away.

If the Premier League data isn't available, the model falls back to raw xG, which includes penalties, and doesn't project penalties separately, so nothing is double-counted.

Player and team IDs in the Premier League API are the same Opta codes FPL exposes as `code`, so the two sources join without any name matching.

### 5. Bonus

Bonus points go to the three highest Bonus Points System (BPS) scores in each match (3, 2, 1). The model projects BPS rather than past bonus points. Past bonus is lumpy: a player can score 27 BPS every week and get nothing because someone else scored 30.

1. **Base BPS.** Every past BPS score is split into the part from goals, assists, clean sheets, goals conceded, saves and missed penalties (using the BPS values: goal 12/12/18/24 for GK/DEF/MID/FWD, assist 9, clean sheet 12, goal conceded −4, save 2, missed penalty −6). The remainder is his **base BPS**: passes, tackles, recoveries, minutes and so on. The model learns a base-BPS-per-90 rate like any other rate. Penalty goals come out with the goals, so a spot kick doesn't inflate it.
2. **This fixture's BPS.** Conditional on starting, his BPS in a match is his base BPS plus whatever he does in *that* fixture. Goals come from open-play xG plus expected penalty goals, assists from xA, a clean sheet or goals conceded from the opponent's expected goals, and saves from the save rate. So bonus rises in easier fixtures, like the returns that drive it.
3. **Scenarios, not averages.** Bonus is a threshold (almost nothing below ~25 BPS, about one point near 29, nearly three from ~45), so the average BPS isn't enough. The model works through the likely outcomes: 0–3 goals, 0–2 assists, a clean sheet or not, and a spread of good and bad base-BPS days (standard deviation learned from the data, about 5). Each outcome's BPS is converted to expected bonus with a **BPS → bonus curve learned from this season's matches**, forced to be non-decreasing, with a sensible default before there's enough data.
4. **Zero-sum.** Each match hands out about 6.3 bonus points (3+2+1, plus ties). Each fixture's projected bonus is scaled so its players share that total. The scenarios decide *who* is likely to get it; the known total fixes *how much* there is.

### Putting a fixture together

For a player in one fixture (`xmins` = expected minutes):

- **Opponent context.** Attacking context = opponent's defence × venue factor. Defensive context = opponent's attack ÷ venue factor.
- **Goals / assists:** open-play xG per 90 × xmins/90 × attacking context, times the position's goal points (GK 10, DEF 6, MID 5, FWD 4). Assists are the same with xA, at 3 points each.
- **Penalties:** expected penalties taken (see above) × (78% × goal points − 22% × 2).
- **Expected goals conceded:** league average × opponent attack × own defence × venue, plus the opponent's expected penalty xG. This is then scaled by how many goals xG has actually turned into this season, shrunk towards 1:1 by 150 xG's worth of prior (0.94 as of gameweek 6). Player expected goals get the same scaling.
- **Clean sheet:** P(60+ minutes) × P(team concedes 0). Goals conceded follow a **negative binomial**, not a Poisson (`goals_dispersion = 6`): P(0) = (1 + expected conceded ÷ 6)^−6. The expected goals for a match are only an estimate, and that uncertainty makes 0-0s more likely than a plain Poisson with the same average says. Checked against gameweeks 2–5: the plain Poisson predicted clean sheets in 22% of team-matches when 30% happened; with this change it predicts 26%, and the backtest's error on points (RMSE) improves.
- **Goals conceded / saves:** exact expectations of −1 per 2 goals conceded (GK/DEF, same negative binomial) and +1 per 3 saves (GK).
- **Defensive contribution:** 2 × P(start) × P(defensive actions ≥ 10 for defenders, 12 for midfielders/forwards). Expected actions = defensive actions per 90 × minutes if he starts ÷ 90 × the opponent's defensive-actions-allowed multiplier. The count in a match follows a **negative binomial** (`defcon_dispersion = 15`): a Poisson whose rate is itself uncertain, for the same reason as goals conceded. Checked on gameweeks 3–5 (381 defender and midfielder games): the Poisson predicted the threshold being reached 23% of the time when 25% happened; with the opponent multiplier and the negative binomial it predicts 24%, and the probability scores (Brier, log loss) improve by 2–3%. Players' own game-to-game consistency was also tested: a player whose counts swing a lot in some games doesn't keep doing so in others (correlation 0.14 between alternate games), so it isn't modelled.
- **Appearance / cards:** P(appear) + P(60+); yellow-card rate × xmins/90.
- **Bonus:** from projected BPS in the fixture (see above).

A gameweek's expected points is the sum over the player's fixtures in it: zero for a blank, two fixtures' worth for a double.

## The star rating

The star rating is **relative to the week**. It is built from expected points per gameweek over the next five gameweeks (a blank gameweek counts as zero):

```
typical = median expected points per gameweek among regular starters
          (players expected to average 60+ minutes a gameweek)
best    = the highest projection this week

star = 5 + 5 × (expected − typical) ÷ (best − typical)      (clamped to 0–10)
```

So a typical regular starter is a 5, the best projection is a 10, and the same line continues below 5 down to 0. The scale is the same for every position.

Expected points are averages, so they sit in a narrow band: roughly 3–6 a gameweek for anyone worth picking, while the best players' actual points per game run higher because they include hauls. An absolute scale starting at 0 points squeezed every realistic option into the top half of the stars. Anchoring the scale to this week's pool spreads them out.

The catch is that a player's stars can move slightly from week to week even if his own projection doesn't, and there is always a 10. The expected points themselves are shown next to the stars everywhere, so the absolute number is never lost. Price is not an input; the Rankings page shows expected points per £m separately.

## Backtest

[`projections/backtest.py`](../projections/backtest.py) replays the season. For each finished gameweek *T* it fits the model on gameweeks before *T* only, predicts *T*, and compares with what happened. There are two simple baselines, points per team match over the last four gameweeks ("form") and over the season. Players are included if they played in *T* or in either of the two gameweeks before it.

Results for 2026-27 gameweeks 2–5 (1,504 player-gameweeks):

| Method | MAE | RMSE | Rank correlation | Avg. points of top 20 picks | Bias |
|---|---|---|---|---|---|
| **Projection model** (prices + last season's history) | **1.92** | **2.74** | **0.45** | **5.25** | −0.14 |
| Without history (price priors only) | 1.92 | 2.75 | 0.45 | 5.00 | −0.13 |
| Without history or price priors | 1.93 | 2.78 | 0.44 | 4.88 | −0.16 |
| First version (bonus from past bonus points, no penalty split) | 1.92 | 2.79 | 0.43 | 4.47 | −0.23 |
| Form (last 4 GWs) | 2.22 | 3.30 | 0.35 | 4.22 | −0.03 |
| Season points per match | 2.22 | 3.30 | 0.35 | 4.22 | −0.03 |

The model's errors are about 13% smaller and it orders players noticeably better. It runs slightly low: it predicts about 0.2–0.25 points per player-gameweek under the actual average.

The penalty split and the BPS-based bonus barely move the headline numbers so far. Only nine penalties had been taken, and bonus is a small share of total points. They are there for the reasons given above: they stop lucky spot kicks and lucky bonus from being read as ability, and they make both respond to the fixture. Their effect on who is ranked where is much larger than their effect on the average error.

Caveats:

- Four gameweeks is a very small sample; with only five played, the "form" and "season" windows are identical.
- The backtest runs without FPL's availability flags, because past flags aren't stored.
- It uses today's penalty order for every past gameweek, because past orders aren't stored either.
- The price priors use start-of-season prices, which were fixed before any of the games being predicted. (The figures above were produced from a data snapshot without start prices, using current prices instead. Re-running on 0.5m price bands, which removes nearly all in-season price movement, gave the same improvement.)

Re-run it as the season goes on with `python projections/backtest.py` to see whether the gap holds and to tune the settings in `ModelConfig`.

**Prior settings** (`python projections/backtest.py --compare-priors`, gameweeks 2–5):

| Setting | MAE | RMSE | Rank correlation | Top 20 picks | Bias |
|---|---|---|---|---|---|
| **Last season, 8 × 90s (chosen)** | 1.917 | **2.739** | **0.451** | **5.25** | −0.14 |
| Last two seasons (older at half), 8 × 90s | **1.909** | 2.742 | 0.449 | 5.01 | −0.18 |
| … weaker (4 × 90s) | 1.909 | 2.744 | 0.449 | 4.88 | −0.18 |
| … stronger (16 × 90s) | 1.909 | 2.741 | 0.449 | 5.18 | −0.19 |
| … stronger (32 × 90s) | 1.910 | 2.742 | 0.449 | 4.99 | −0.19 |
| … no fade | 1.909 | 2.742 | 0.449 | 5.10 | −0.18 |
| No history (price priors only) | 1.918 | 2.748 | 0.449 | 5.00 | −0.13 |
| No history, no prices | 1.933 | 2.780 | 0.437 | 4.88 | −0.16 |

Prices were the big step. History adds a little more, and how heavily it's weighted barely matters yet. Last season alone won on RMSE, ranking and top-20 picks, and was the least biased of the history options, so it's the default. Adding the season before improved MAE only. MAE rewards predicting the typical (often low) score rather than the average, so it's the less relevant measure for expected points. Differences this small are within the noise of four gameweeks; re-run the comparison mid-season.

## Known limitations and next steps

- **Pre-season information comes only from prices.** Start-of-season prices stand in for last season's data. They're a good summary but a blunt one: they don't know about a player's new role, and they're capped and rounded by FPL.
- **Top teams' clean sheets** are still under-predicted: in the backtest, the most expensive goalkeepers scored about 1.6 points per game more than predicted.
- **Double gameweeks in history.** The live endpoint gives one combined row per player per gameweek, so a past double gameweek's xG is split evenly across its two matches.
- **Other set pieces.** Corner and free-kick takers aren't modelled separately. Their extra chances come from a stable role, so they are already reflected in their xA and xG.
- **Penalty saves** aren't modelled for goalkeepers.
- **Bonus** treats goals, assists and clean sheets as independent within a match, and it doesn't model how other players' BPS in the same match moves the threshold beyond scaling each match to its usual total.
- **Minutes** are learned from recent selections only, so a player returning from injury is under-projected for a week or two.
