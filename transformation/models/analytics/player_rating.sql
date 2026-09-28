{{ config(materialized='table') }}

-- =============================================================================
-- ROUND 7 REWRITE -- new rating philosophy, same tunable-weights convention.
--
-- The previous version of this model blended five ingredients: season
-- quality, last-5-gameweek form, the player's team's own match RESULTS,
-- how highly other teams rated this team as an opponent, and next-5
-- fixture difficulty. That was a reasonable first cut, but it had three
-- problems worth fixing:
--
--   1. "Season quality" vs "last-5 form" is an arbitrary two-bucket
--      split. A player's gameweek 3 form and gameweek 30 form don't
--      actually matter equally just because they both fall inside or
--      outside one hard window -- gameweek 29 should count for
--      *slightly* less than gameweek 30, not the same as gameweek 3.
--      This rewrite replaces the two hard buckets with one continuous
--      exponential recency decay (gw_decay below), so "how good is this
--      player right now" fades smoothly from the most recent match back
--      through the whole season, instead of jumping off a cliff at an
--      arbitrary 5-gameweek line.
--
--   2. "Team results" (win/draw/loss) rewards a team for grinding out
--      scrappy 1-0s, which is exactly the kind of thing that regresses --
--      it's an outcome, not an underlying process. This rewrite replaces
--      it (and the old "team strength" ingredient, which proxied
--      strength via how hard opponents *found* this team rather than
--      anything about the team itself) with the team's own underlying
--      npxG created and xG conceded rates -- the same "process over
--      results" idea already used for individual players in
--      player_points_expected below, just applied one level up at the
--      team. A team out-performing its underlying attacking numbers is
--      as likely to come back down as an individual player is.
--
--   3. Fixture difficulty used FPL's own crowd-sourced 1-5 difficulty
--      rating, which is a reasonable general-purpose number but isn't
--      tied to anything else in this model. This rewrite instead scores
--      each of the next 5 fixtures using the SAME underlying team
--      attack/defence rates computed for ingredient 2 above, applied to
--      the OPPONENT -- so "team strength" and "fixture outlook" are now
--      two views of one consistent set of team-level numbers, not two
--      unrelated difficulty concepts.
--
-- What DIDN'T make it into this rewrite, and why: set-piece and penalty
-- duty (who's on penalties, corners, free kicks) would be a genuinely
-- good predictive signal -- a nailed-on penalty taker has a sticky
-- scoring edge no amount of open-play xG captures. It isn't included
-- here because there is no such data anywhere in this project's raw
-- sources: stg_players.sql and stg_player_gameweek.sql were both
-- checked, and neither the player dimension nor the per-gameweek stats
-- carry a penalty-order, corner-order or free-kick-order column (the FPL
-- API does expose these on some endpoints, but this project's
-- raw_players extract doesn't capture them). Rather than fabricate a
-- signal this project has no data for, this is called out explicitly so
-- it's easy to find and wire in later: if a future extraction adds
-- e.g. raw_players.penalties_order, the place to add it is a new
-- ingredient alongside quality_score below, gated to MID/FWD.
--
-- Price/value is still deliberately kept out of this model entirely, as
-- before -- this produces a pure "how good is this player going
-- forward" rating, with price-adjusted value left to the separate
-- ppm90 metric in queries/player_stats.py. A £4m player and a £14m
-- player with the same underlying numbers should get the same star.
--
-- ROUND 7.1 follow-up (two feedback-driven fixes on top of the above):
--
--   1. blend_score (the direct weighted blend) compressed hard against
--      the top of the scale -- nobody in the game landed above ~8.5,
--      however good their numbers were, because averaging four only
--      loosely-correlated 0-10 scores rarely lands near 10 even for a
--      genuinely excellent player (their own quality being elite
--      doesn't mean their team's fixtures are too). Fixed by
--      re-expressing blend_score as one more within-position percentile
--      -- see blend_scores/underlying_scores below (Round 8 later
--      reverted this specific percentile rescale -- see the ROUND 8
--      note further down).
--
--   2. Not every midfielder is a realistic defensive-contribution
--      candidate -- an out-and-out attacking midfielder essentially
--      never gets near that bonus. Rather than hardcode specific
--      players' names, MID_DEFCON_ROLE_THRESHOLD decides this from each
--      player's own recency-weighted defensive-action rate, redirecting
--      that ingredient's weight onto quality for anyone below it -- see
--      component_scores' quality_weight/defcon_weight columns.
--
-- ROUND 7.2 follow-up: a barely-played player at a strong team with
-- good fixtures (e.g. an injury-hit midfielder just starting to come
-- back) was still landing a surprisingly high star, because Round 7.1's
-- fix applied the minutes-security gate BEFORE the percentile rescale --
-- a gated-down player could still land in the *middle* of the
-- distribution if enough other players had similarly middling blend
-- scores, since percent_rank only preserves relative order, not how far
-- below the pack a heavily-gated player really is. Fixed by rescaling
-- blend_score to a percentile FIRST (giving a clean "how good is this
-- player ignoring reliability" number out of 10), and only THEN
-- applying the minutes-security multiplier -- see underlying_scores/the
-- final select below (Round 8 removed the underlying_scores CTE itself,
-- but kept this ordering -- the gate still runs AFTER blend_score, on
-- blend_score directly now -- see the ROUND 8 note further down).
--
-- ROUND 7.3 follow-up: the minutes-security gate used to average the
-- last 5 gameweeks' minutes flatly, so a player who'd been out injured
-- and had since returned to full minutes stayed penalised for a month
-- by the injury-affected gap sitting equally-weighted alongside their
-- fresh appearances. Fixed with a new, much steeper decay
-- (MINUTES_DECAY_RATE, minutes_decay below) specifically for this gate,
-- so the very latest gameweek dominates the reliability read and a
-- recovered player's score climbs back towards trustworthy within a
-- game or two.
--
-- ROUND 7.4 follow-up: quality now adjusted for the strength of the
-- opposition faced so far, not just raw output. A goal against a poor
-- defence and a goal against a great defence previously counted exactly
-- the same towards quality_actual_score/quality_expected_score -- this
-- adds a per-match opponent-difficulty multiplier (built the same way as
-- team_strength_score/fixture_outlook_score's own attack/defence
-- percentiles above, just applied to a PAST opponent instead of an
-- upcoming one) so tougher opposition is worth more, weaker opposition
-- worth less. Computed leave-one-out: the specific match a player's team
-- played against an opponent is excluded from that opponent's OWN
-- attack/defence numbers before using them to grade that same match --
-- otherwise a single scoreline would partly be marking its own homework
-- (e.g. if Coventry conceded heavily in one match, that same match would
-- both make the scoring player's numbers look better AND drag down the
-- very "how strong was this defence" figure used to grade that
-- performance). Concretely, this means Coventry's effective strength
-- when adjusting an Arsenal player's numbers is not the same figure used
-- to adjust a Brighton player's numbers, even though both played
-- Coventry -- each excludes its own fixture. See team_gw_loo_rates/
-- team_gw_opponent_difficulty/player_gw_opponent_multiplier below. No new
-- column is exposed on the final output for this -- it's a refinement of
-- what quality_actual_score/quality_expected_score already mean, not a
-- fifth ingredient, so the existing breakdown UI and Streamlit queries
-- need no changes.
--
-- ROUND 7.5 follow-up: team_attack_score/team_defence_score (and, by
-- extension, the strength-of-opposition adjustment above, which is built
-- from the same numbers) were sharing FORM_DECAY_RATE with individual
-- player quality -- too reactive for a team-level signal. Traced through
-- a real example: Man City sitting 2nd-worst in the league on
-- team_defence_score despite only a below-average season-long xG-
-- conceded total, caused by one bad recent game (at the maximum
-- possible recency weight, on top of a small early-season sample)
-- dominating the whole rate. Fixed with a new, slower, dedicated decay
-- (TEAM_STRENGTH_DECAY_RATE, team_strength_decay below) -- a team's
-- underlying attacking/defensive process is a squad-wide, structural
-- property that shouldn't swing on one outlier match the way an
-- individual's form or fitness genuinely can. See team_gw_contribution
-- below.
--
-- ROUND 7.6 follow-up: the same "one recent game at max weight, tiny
-- early-season sample" mechanism that drove Round 7.5, but at the
-- individual-player level -- Brian Brobbey rated the #1 striker despite
-- almost no output across his first 4 gameweeks, purely off one big
-- gameweek 5. FORM_DECAY_RATE raised from 0.87 to 0.90 -- still more
-- reactive than TEAM_STRENGTH_DECAY_RATE, deliberately, since individual
-- form/fitness genuinely can shift faster than a team's tactical
-- identity, just not as reactive as it was.
--
-- ROUND 8: percent_rank() replaced everywhere with a magnitude-preserving
-- z-score scale -- feedback that the percentile approach "doesn't show
-- relative difference between the top players very well", and that a
-- standout in-form player (Pascal Groß specifically) should be able to
-- reach 9-10 more easily than the old scale allowed.
--
-- The problem with percent_rank() was never really about compression at
-- the ingredient level -- the single best player in any one ingredient
-- already scored a full 10 under percentiles, same as under this
-- change. The real problem is that percent_rank() only encodes RANK, not
-- MAGNITUDE: two players three places apart in the table get scored the
-- same distance apart whether their underlying numbers are almost
-- identical or genuinely miles apart, and a handful of real outliers at
-- the very top get flattened into the same evenly-spaced ladder as
-- everyone in the crowded middle of the table. That's exactly "doesn't
-- show relative difference between the top players very well".
--
-- Every percent_rank() in this model is now a z-score instead: how many
-- standard deviations a player's (or team's) raw rate sits from the mean
-- of the relevant population (within position for player ingredients,
-- across all 20 teams for team strength), linearly mapped onto 0-10
-- around a centre of 5 and clamped at the ends (see SCORE_SD_SPAN below).
-- This preserves genuine gaps -- several players who are all comfortably
-- ahead of the pack can now ALL land near 9-10 together, rather than
-- being spread out one rank at a time purely because only one of them
-- can hold the literal #1 spot -- while a small handful of true outliers
-- doesn't need to be "the best of 400" to get there, just genuinely many
-- standard deviations better than average.
--
-- Also reverted: blend_score (the weighted combination of the four
-- ingredients) is no longer rescaled to a percentile at all -- the
-- Round 7.1/7.2 "underlying_scores" step is gone, and blend_score itself
-- (clamped to 0-10) is now the star, before the minutes-security gate.
-- This was explicitly asked for ("revert it back to when it wasn't
-- really using percentile like that"), and it's worth being upfront
-- about the trade-off it brings back: blend_score is an average of four
-- only loosely-correlated ingredients, so a player who's genuinely
-- excellent at one thing (say, quality) but only average on team
-- strength or fixtures that week will still get pulled down by the
-- ones they aren't excelling at -- reaching 9-10 now takes being
-- properly good across most of what's blended in, not just brilliant on
-- one axis. Z-scores make that materially easier than percentiles did
-- (see above -- several genuinely elite players can now all score near
-- 10 on quality itself, rather than only the outright #1), but it isn't
-- a guarantee for every in-form player regardless of their team/fixture
-- picture -- if this still caps out lower than expected once it's live,
-- the next lever is raising QUALITY_ACTUAL_WEIGHT/QUALITY_EXPECTED_WEIGHT's
-- effective share of the blend for the position in question, not
-- reintroducing a rank-based rescale.
--
-- Two more small, related changes: (1) quality_rates' raw per-90 figures
-- (actual_p90/expected_p90 -- an actual points-per-90 NUMBER, not a 0-10
-- score) are now carried through to the final output as
-- actual_points_p90/expected_points_p90. These were originally added so
-- a separate player_expected_points.sql model could reuse this model's
-- already-computed recency-weighted quality rate instead of recomputing
-- it -- that model was removed again in Round 9 (see the CHANGELOG), but
-- the two columns were left in place, since they're reasonable per-90
-- rates to expose in their own right regardless of what consumed them.
-- (2) team_gw_opponent_difficulty (the leave-one-out strength-of-
-- opposition adjustment from Round 7.4) is rebuilt on the same z-score
-- scale for consistency -- it used to manually replicate what
-- percent_rank works out to for an out-of-sample value; it's now a much
-- shorter direct z-score against the same team population, same idea as
-- everywhere else in this round.
-- =============================================================================
--
-- ROUND 9: removed the next-5-fixtures expected-points feature this
-- model was feeding (player_expected_points.sql, and the xPts numbers
-- on the Player/Compare pages) -- feedback that the numbers weren't
-- earning their keep. No change to this model itself beyond the note
-- above; see the CHANGELOG for the full removal.
--
-- ROUND 10: DEF_WEIGHT_DEFCON used to apply to every defender flatly,
-- unlike midfielders, who already had a self-adjusting threshold
-- (MID_DEFCON_ROLE_THRESHOLD, Round 7.1) redirecting that weight onto
-- quality for anyone who was never a realistic defensive-contribution
-- candidate. Feedback: some defenders genuinely aren't defcon
-- candidates either -- an attacking wing-back or a ball-playing centre-
-- back pushed forward (Calafiori was the example raised) -- and
-- shouldn't have their rating held down by an ingredient that was never
-- a realistic part of their game. Defenders now get the exact same
-- self-adjusting treatment, gated on their own recency-weighted
-- defcon_p90 against a defender-specific threshold (see
-- DEF_DEFCON_ROLE_THRESHOLD below, set lower than the midfielder
-- threshold to match the lower real bonus threshold defenders actually
-- play under). See component_scores' defcon_weight/quality_weight
-- columns further down.
--
-- ROUND 11: expected_points (in player_points_expected below) used to
-- include the clean-sheet bonus (pf_cs) completely unswapped -- the
-- actual result, not a process estimate, even though this whole
-- ingredient exists specifically to reward the underlying process
-- rather than the fluky outcome. That's a real inconsistency for
-- goalkeepers and defenders specifically (clean sheets are their
-- single biggest scoring route, and a midfielder's smaller clean-sheet
-- bonus too): a team that rode a lucky, high-xG-conceded clean sheet
-- got full credit in "expected" quality exactly as much as in "actual"
-- quality, unlike goals/assists/goals-conceded, which already had a
-- genuine xG/xA/xGA-based substitute. Fixed by replacing pf_cs with an
-- expected-clean-sheet points estimate: exp(-pg_xGa) as the clean-sheet
-- probability under a Poisson model of goals conceded, multiplied by
-- the real points-per-clean-sheet for the position (4 for GK/DEF, 1 for
-- MID, 0 for FWD, matching pf_cs's own scoring exactly). See the full
-- note on player_points_expected below for the one known limitation
-- (a double gameweek's combined xGa can't be split back into "which of
-- the two matches was the clean sheet").
--
-- ROUND 12: fixture_outlook_score was never really "next 5 fixtures" --
-- next5 (below) had no row limit at all despite its own comment saying
-- otherwise, so it was pulling in every remaining gameweek of the
-- season, just decayed down by FIXTURE_DECAY_RATE rather than excluded.
-- Found while diagnosing why the fixture-outlook ingredient looked
-- inconsistent comparing a few teams' defenders side by side. Fixed
-- with a genuine "top (5)" limit -- see the note on next5 itself below
-- for the full explanation.
--
-- ROUND 13: fixing Round 12 above wasn't enough -- feedback (correctly)
-- pushed back that fixture_outlook_score still looked "squeezed", with
-- every team landing around 5-6 regardless of how genuinely easy or
-- hard their next 5 games actually were. The real cause: this ingredient
-- averages 5 DIFFERENT opponents' z-scores together, and averaging
-- several samples from one population mechanically shrinks the spread
-- of that average -- a standard statistical fact, nothing to do with
-- how many fixtures were included. A first attempt at fixing this only
-- reordered WHEN the 0-10 mapping happened (average the raw z's, map
-- once, instead of mapping each opponent then averaging) -- genuinely
-- correct as far as it went, but it turned out not to be the dominant
-- effect: re-mapping an already-narrower average back onto the SAME
-- scale calibrated for a single team's full-season rate still comes out
-- compressed, because the scale was never the problem -- the reference
-- population was. The actual fix: z-score each team's blended-next-5-
-- opponents figure against the population of every OTHER team's OWN
-- blended-next-5 figure (team_fixture_population below), not against
-- team_rate_population (built for a different quantity -- a team's own
-- single-season rate -- with a different natural spread). See
-- team_fixture_raw_z/team_fixture_population/team_fixture_outlook
-- further down for the full mechanics.
-- =============================================================================


-- =============================================================================
-- TUNABLE WEIGHTS -- this is the only section you should need to touch to
-- try different pictures of "how good is this player to transfer in".
-- =============================================================================

-- Each position gets its own blend of four 0-10 ingredients (quality,
-- defensive contribution, team strength, fixture outlook), rather than
-- one global weight set applied identically everywhere -- a goalkeeper's
-- rating should be dominated by their team's defensive solidity in a way
-- a forward's never is, and a forward's should be dominated by their own
-- attacking numbers in a way a goalkeeper's never is. Each position's
-- four weights must sum to 1.0.
--
-- Goalkeeper: there is close to nothing a keeper's OWN underlying stats
-- can tell you that isn't really "how solid is this team defensively" --
-- saves are largely a function of facing more shots, not skill, and
-- clean sheets are a team property. So team strength (their own
-- defensive rate) and fixture outlook (upcoming opponents' attacking
-- weakness) dominate; defensive-contribution points don't exist for
-- goalkeepers under the scoring rules at all, so that weight is 0.
{% set GK_WEIGHT_QUALITY        = 0.40 %}
{% set GK_WEIGHT_DEFCON         = 0.00 %}
{% set GK_WEIGHT_TEAM_STRENGTH  = 0.35 %}
{% set GK_WEIGHT_FIXTURES       = 0.25 %}

-- Defender: a genuine split personality position under the new scoring
-- rules -- a clean-sheet/defensive-contribution defender and an
-- attacking-fullback-who-chips-in-goals defender can both be excellent
-- picks via completely different routes, which is exactly why quality
-- (their own actual output, whichever route it comes from) and
-- defensive-contribution rate both get real weight here, alongside
-- team/fixture outlook which still matters a lot for the clean-sheet
-- income every defender shares.
{% set DEF_WEIGHT_QUALITY       = 0.35 %}
{% set DEF_WEIGHT_DEFCON        = 0.15 %}
{% set DEF_WEIGHT_TEAM_STRENGTH = 0.25 %}
{% set DEF_WEIGHT_FIXTURES      = 0.25 %}

-- Midfielder: the most balanced position -- own output dominates (it's
-- the biggest scoring route for most midfielders), with a meaningful
-- defensive-contribution slice now that under-the-radar defensive
-- midfielders can rack up real points from tackles/recoveries, and
-- team/fixture effects mattering less than for the more team-dependent
-- positions above.
{% set MID_WEIGHT_QUALITY       = 0.45 %}
{% set MID_WEIGHT_DEFCON        = 0.15 %}
{% set MID_WEIGHT_TEAM_STRENGTH = 0.15 %}
{% set MID_WEIGHT_FIXTURES      = 0.25 %}

-- Forward: dominated by their own output (goals/xG) and by the fixture
-- in front of them -- an in-form forward against a leaky defence is
-- close to the whole story. Defensive contribution is switched off: it's
-- not a meaningful signal for how good a forward pick is, and weighting
-- it would just reward a forward for tracking back rather than for
-- doing the job that actually wins a squad points.
{% set FWD_WEIGHT_QUALITY       = 0.55 %}
{% set FWD_WEIGHT_DEFCON        = 0.00 %}
{% set FWD_WEIGHT_TEAM_STRENGTH = 0.15 %}
{% set FWD_WEIGHT_FIXTURES      = 0.30 %}

-- Within "quality": how much weight goes on what actually happened
-- (actual points) vs what the underlying process says should have
-- happened (expected points, from xG/xA/xGA). Weighted further towards
-- expected than the old model's 0.45/0.55 split -- this whole rewrite is
-- explicitly framed around being predictive rather than historical, so
-- it leans further into "what does the process say is repeatable"
-- rather than "what's already been banked". Must sum to 1.0.
{% set QUALITY_ACTUAL_WEIGHT    = 0.40 %}
{% set QUALITY_EXPECTED_WEIGHT  = 0.60 %}

-- Each position's split between caring about its OWN TEAM'S attacking
-- output vs defensive solidity -- used both for team_strength_score (the
-- player's own team, right now) and fixture_outlook_score (the next 5
-- opponents' equivalent numbers, inverted -- see team_fixture_raw_z
-- below). A forward lives and dies by their team creating chances; a
-- defender/keeper lives and dies by their team not conceding them;
-- midfielders (and attacking-minded defenders) sit in between. Round
-- 7.4 also reuses this same split for the strength-of-opposition
-- adjustment below (player_attack_share) -- the same lean that decides
-- how much a player's OWN team's attack/defence matters also decides how
-- much of "how tough was this match" comes from the opponent's defence
-- vs the opponent's attack.
{% set GK_TEAM_ATTACK_SHARE  = 0.00 %}
{% set DEF_TEAM_ATTACK_SHARE = 0.15 %}
{% set MID_TEAM_ATTACK_SHARE = 0.93 %}
{% set FWD_TEAM_ATTACK_SHARE = 1.00 %}

-- Recency decay rates -- how much one gameweek further back is worth,
-- multiplicatively, relative to the gameweek after it. Applied per
-- gameweek, so e.g. 0.90 means 10 gameweeks ago counts for 0.90^10 ~= 35%
-- of last week. Separate rates because they're answering different
-- questions: FORM_DECAY_RATE governs "how good is this INDIVIDUAL PLAYER
-- right now" (a slower fade -- a whole season of data is still
-- informative, just increasingly diluted); FIXTURE_DECAY_RATE governs
-- "how much does gameweek+5's difficulty matter compared to
-- gameweek+1's" (a much steeper fade, since a squad's form and a
-- fixture's context can shift a lot over even a month, and gameweek+1 is
-- simply far more certain/actionable than gameweek+5 for a transfer
-- decision made today); TEAM_STRENGTH_DECAY_RATE (set further below)
-- governs a team's own underlying attack/defence rate specifically.
--
-- Round 7.6: FORM_DECAY_RATE raised from 0.87 to 0.90 (10 gameweeks ago
-- now counts for ~35% of last week, up from ~25%). Feedback: Brian
-- Brobbey was rated the #1 striker despite barely registering a shot's
-- worth of xG across his first 4 gameweeks, purely on the strength of
-- one big gameweek-5 haul -- the same "one recent game at the maximum
-- possible weight, on a tiny early-season sample" mechanism that drove
-- the Round 7.5 team-strength fix, just at the individual-player level
-- this time. Widened the same way, though deliberately less drastically
-- than TEAM_STRENGTH_DECAY_RATE's 0.95 -- an individual player's form
-- and fitness genuinely can shift faster than a whole team's underlying
-- tactical identity, so this should stay more reactive than team
-- strength, just not as reactive as it was. Worth being honest about
-- the limits of this fix, though: quality is a PER-90 rate
-- (points-per-90-minutes-played, not points-per-game), so if a player's
-- earlier gameweeks were mostly low-minute cameos rather than genuine
-- quiet full games, they carry little weight in the per-90 average
-- regardless of how recency itself is tuned -- one huge full-90 haul
-- can still dominate a small, minutes-light sample even after this
-- change. If a case like Brobbey's still looks wrong once this is live,
-- the next lever to reach for is a minimum-GAMES (not just
-- minimum-total-minutes) floor on MIN_MINUTES_FOR_FORM_RATE, not a
-- further decay change.
{% set FORM_DECAY_RATE    = 0.93 %}
{% set FIXTURE_DECAY_RATE = 0.90 %}

-- Round 7.5: a TEAM's underlying attack/defence rate gets its own,
-- slower decay than FORM_DECAY_RATE above, rather than sharing it.
-- Feedback (working through a real example -- Man City sitting 2nd-worst
-- in the league on team_defence_score despite a merely below-average
-- season-long xG-conceded total) showed FORM_DECAY_RATE=0.87 is too
-- reactive for this specific ingredient early in a season: with only a
-- handful of gameweeks played, the most recent one carries the maximum
-- possible weight (1.0), so a single bad defensive performance can swing
-- the whole recency-weighted rate a long way on a tiny sample --
-- checking the actual gameweek-by-gameweek numbers, one game at 3.02 xGA
-- (roughly 2.5x their other games that season) was, on its own, enough
-- to pull City from a below-average-but-unremarkable season rate up to
-- 2nd-worst in the league. FORM_DECAY_RATE is deliberately left as it
-- was for individual player quality -- a player's own current form/
-- fitness genuinely can flip fast -- but a whole team's underlying
-- attacking/defensive process is a squad-wide, tactical, more
-- STRUCTURAL property that doesn't swing on one freak result (an off
-- day, a red card, a tactical mismatch) the way a player's individual
-- game-to-game output can. 0.95 means 10 gameweeks ago still counts for
-- 0.95^10 ~= 60% of last week -- close enough to a flat season average
-- that recent form still nudges the number, without one outlier game
-- dominating a small early-season sample the way 0.87 did.
{% set TEAM_STRENGTH_DECAY_RATE = 0.95 %}

-- Minimum total minutes played this season before a per-90 rate (quality
-- or defensive contribution) is trusted at all -- below this, treated as
-- "no data" (0) rather than a small-sample rate that one cameo goal
-- could blow wildly out of proportion.
{% set MIN_MINUTES_FOR_FORM_RATE = 90 %}

-- Round 8: every 0-10 ingredient score in this model (quality, defensive
-- contribution, team attack/defence) is a z-score -- how many standard
-- deviations a player's (or team's) raw rate sits above or below the
-- mean of the relevant population -- linearly mapped onto 0-10 around a
-- centre of 5, then clamped. SCORE_SD_SPAN is how many standard
-- deviations away from the mean reaches the very edge of the scale (0 or
-- 10): 2.5 means +2.5 SD (roughly top ~0.5-1% of a normal-ish
-- population) maps to a full 10, -2.5 SD maps to a full 0, and anything
-- beyond that is clamped rather than running off the scale. A smaller
-- number makes it EASIER to reach the extremes (fewer standard
-- deviations needed); a larger number makes 9-10 rarer and reserved for
-- more extreme outliers. Replaces percent_rank() everywhere in this
-- model -- see the ROUND 8 note at the top of this file for why.
{% set SCORE_SD_SPAN = 2 %}

-- Round 7.1: not every midfielder is a defensive-contribution
-- candidate -- an out-and-out attacking midfielder/winger essentially
-- never gets near the defensive-contribution bonus threshold, so giving
-- them the standard MID_WEIGHT_DEFCON just dilutes their rating with an
-- ingredient that was never a realistic part of their game. Rather than
-- hardcode a list of "attacking" vs "defensive" midfielders by name
-- (which would need manually maintaining every transfer window, and
-- wouldn't cover the whole player pool), this is decided from the
-- player's own recency-weighted defensive-action rate (defcon_p90,
-- already computed in quality_rates above): a midfielder below this
-- threshold has that ingredient's weight folded into their quality
-- weight instead (see component_scores' quality_weight/defcon_weight
-- columns below), fully self-adjusting as a player's role changes.
-- 6 per 90 sits roughly halfway to the 12-action bonus threshold
-- itself (see pf_defcon in player_points.sql) -- comfortably below
-- where a genuine defensive/box-to-box midfielder sits, comfortably
-- above where an attacking midfielder/winger sits. A judgement call,
-- like every other tunable here -- retune if it doesn't feel right for
-- a particular borderline player.
{% set MID_DEFCON_ROLE_THRESHOLD = 6.0 %}

-- Round 10: the same self-adjusting logic as MID_DEFCON_ROLE_THRESHOLD
-- above, now also applied to defenders. An attacking wing-back or a
-- ball-playing centre-back pushed forward (Calafiori was the example
-- raised) realistically never gets near the defensive-contribution
-- bonus either, and previously had no way out of DEF_WEIGHT_DEFCON --
-- every defender was scored on it regardless of whether it was ever a
-- realistic scoring route for them. Decided the same way, from each
-- defender's own recency-weighted defcon_p90: below this threshold,
-- DEF_WEIGHT_DEFCON folds into DEF_WEIGHT_QUALITY instead (see
-- component_scores below), fully self-adjusting per player rather than
-- a hardcoded list. Set lower than MID_DEFCON_ROLE_THRESHOLD -- 5.0
-- rather than 6.0 -- because the underlying FPL bonus threshold itself
-- is lower for defenders: pf_defcon in player_points.sql awards the
-- defensive-contribution bonus at 10 actions for a defender, vs 12 for
-- midfielders/forwards, so 5.0 is the same "roughly halfway to the
-- real bonus threshold" judgement call, just scaled to the defender-
-- specific line rather than reusing the midfielder one.
{% set DEF_DEFCON_ROLE_THRESHOLD = 5.0 %}

-- Minutes-security gate (see minutes_security CTE below) -- applied as a
-- final multiplier on the whole star, not as one blended ingredient
-- among others, because a brilliant underlying rating means nothing if
-- the player isn't actually going to be on the pitch.
{% set MINUTES_PER_MATCH      = 90 %}
{% set MINUTES_SECURITY_FLOOR = 0.3 %}
{% set NEWS_LOOKBACK_DAYS     = 7 %}
{% set INJURY_NEWS_MULTIPLIER = 0.4 %}

-- Round 7.3: how steeply the last 5 gameweeks are weighted for the
-- minutes-security gate specifically -- deliberately much steeper than
-- FORM_DECAY_RATE above. A returning-from-injury (or just recently
-- recalled) player's minutes reliability can flip from "not trusted" to
-- "nailed on" within a single gameweek, unlike underlying quality/team
-- strength, which are slower-moving and benefit from remembering more
-- history. 0.35 means 2 gameweeks ago already counts for little more
-- than a tenth of last week -- so one fresh, fully-played gameweek back
-- from injury pulls this gate most of the way back towards 1.0 on its
-- own, rather than staying dragged down by an old absence for a month.
{% set MINUTES_DECAY_RATE = 0.35 %}

-- Round 7.4: how strongly a player's quality (actual + expected points)
-- is adjusted for the strength of the opposition faced in each
-- individual gameweek, on top of the recency decay above. Expressed as
-- how much more (or less) a performance against the toughest possible
-- opponent (a 10/10 opponent_difficulty_score) is worth, relative to a
-- perfectly average one (5/10, multiplier exactly 1.0) -- 0.30 means the
-- toughest opponent in the league is worth 30% more than average, the
-- weakest opponent 30% less, scaled linearly in between. Set to 0 to
-- turn this off entirely and go back to treating every match equally.
{% set SOS_STRENGTH_FACTOR = 0.30 %}

-- =============================================================================
-- Everything below implements the blend above. You shouldn't need to
-- change anything past this point just to try different weightings.
-- =============================================================================

-- Round 8: the shared z-score-to-0-10 expression used everywhere this
-- model used to call percent_rank() now lives in its own file,
-- macros/zscore_to_10.sql -- see that file for the full explanation and
-- why it isn't (and can't be) defined inline here any more. Every call
-- below passes SCORE_SD_SPAN (set above) as its own explicit argument,
-- since a macro living in a different file has no visibility into a
-- Jinja "set" variable defined up in this file's own tunables block --
-- SCORE_SD_SPAN still lives here, in the tunables block everyone already
-- edits, not duplicated inside the macro itself.

with

-- Every finished gameweek this season, ranked 0 (most recent) upwards,
-- with an exponential recency weight. This single CTE is the source of
-- "how much does this gameweek count" for both a player's own quality/
-- defensive-contribution rate and their team's attack/defence rate --
-- one recency definition, reused everywhere, rather than the old model's
-- separate hard-coded "last 5" window duplicated across several CTEs.
gw_decay as (
    select
        gw_id,
        row_number() over (order by gw_deadline_time desc) - 1 as gws_ago,
        power(cast({{ FORM_DECAY_RATE }} as float), row_number() over (order by gw_deadline_time desc) - 1) as weight
    from {{ ref('gameweeks') }}
    where gw_deadline_time < getdate()
),

-- The next 5 gameweeks, ranked 1 (soonest) upwards, with a steeper
-- proximity weight for the fixture-outlook ingredient.
--
-- Round 12 fix: this comment always said "the next 5 gameweeks", but
-- the query itself had no such limit -- it selected every gameweek with
-- gw_deadline_time > getdate(), i.e. every remaining fixture of the
-- season, each just increasingly discounted by FIXTURE_DECAY_RATE but
-- never actually reaching 0. Found while investigating why fixture_
-- outlook_score looked inconsistent comparing a few teams' defenders
-- side by side -- teams can end up differing for reasons that have
-- nothing to do with their real next 5 games (how their fixtures happen
-- to fall later in the season, how many gameweeks currently exist in
-- the table, etc.), not just genuine near-term difficulty. Fixed with
-- "top (5)", the same pattern already used correctly for this exact
-- purpose in queries/player_info.py's get_next_5 -- now genuinely only
-- the 5 soonest gameweeks are selected at all, so anything beyond that
-- horizon has a weight of 0 by not being included, rather than a
-- vanishingly small but nonzero one.
next5 as (
    select top (5)
        gw_id,
        row_number() over (order by gw_id) as gws_ahead,
        power(cast({{ FIXTURE_DECAY_RATE }} as float), row_number() over (order by gw_id) - 1) as weight
    from {{ ref('gameweeks') }}
    where gw_deadline_time > getdate()
    order by gw_id
),

-- The most recent 5 finished gameweeks, each with its OWN recency
-- weight for the minutes-security gate below -- see MINUTES_DECAY_RATE
-- above for why this needs a separate, steeper decay from gw_decay's
-- weight rather than reusing it directly.
minutes_decay as (
    select
        gw_id,
        power(cast({{ MINUTES_DECAY_RATE }} as float), gws_ago) as weight
    from gw_decay
    where gws_ago < 5
),

-- Round 7.5: every played gameweek, with its OWN, much slower recency
-- weight specifically for team-level attack/defence strength -- see
-- TEAM_STRENGTH_DECAY_RATE above for why this needs to be gentler than
-- gw_decay's own weight (which stays exactly as before for individual
-- player quality). No gws_ago cutoff, unlike minutes_decay -- a team's
-- whole season is still worth remembering, just increasingly diluted,
-- the same "informative but fading" shape gw_decay itself has, just at
-- a slower rate.
team_strength_decay as (
    select
        gw_id,
        power(cast({{ TEAM_STRENGTH_DECAY_RATE }} as float), gws_ago) as weight
    from gw_decay
),

-- Per-player-per-gameweek actual points (from player_points, the
-- project's single source of truth for "what counts as fantasy points")
-- alongside an *expected* points figure built with the same formula, but
-- swapping in xG/xA/xGA wherever an underlying-process stat exists
-- (goals, assists, goals conceded, and -- Round 11 -- clean sheets).
--
-- Round 11: pf_cs (the real clean-sheet bonus: 4/8 pts for GK/DEF on a
-- single/double clean sheet, 1/2 for a midfielder, 0 for a forward --
-- see pf_cs in player_points.sql) used to be included in expected_points
-- completely unswapped, i.e. counted as itself, the actual result, not a
-- process estimate. That quietly broke this model's own stated
-- principle for two whole positions: clean sheets are the single
-- biggest scoring route for goalkeepers and defenders, and a lucky
-- clean sheet a team barely deserved (high xG conceded, low actual goals
-- against) was getting full credit in "expected" quality exactly as much
-- as in "actual" quality -- no smoothing at all, unlike goals/assists/
-- goals-conceded, which all already had a genuine process-based
-- substitute. Fixed by replacing pf_cs here with an expected-clean-sheet
-- points estimate: model each match's goals-conceded as Poisson-
-- distributed with mean pg_xGa (a standard, widely-used approximation),
-- so the probability of a clean sheet is exp(-pg_xGa), and multiply that
-- probability by the real points-per-clean-sheet for this position (4
-- for GK/DEF, 1 for a midfielder, 0 for a forward, matching pf_cs
-- exactly). A team expected to concede 0.3 goals has a genuinely good
-- (74%) expected clean sheet; a team expected to concede 2.0 goals has a
-- poor one (14%) even if they happened to keep the sheet clean that day.
--
-- Known limitation, honestly: pg_xGa (like pg_clean_sheets) is a single
-- combined figure per gameweek, already summed across both matches on a
-- double gameweek -- there's no per-match breakdown available this far
-- downstream (see stg_player_gameweek.sql/player_stats.sql, which pull
-- it straight from the FPL API's own per-gameweek aggregate). Under a
-- Poisson-independence assumption, exp(-total_xGa) does work out to the
-- correct probability of a genuine DOUBLE clean sheet (zero conceded in
-- both matches), but it can't separately capture "clean sheet in one
-- match, not the other" the way pf_cs's own linear 1-clean-sheet-vs-2
-- structure does for actual results -- a rare edge case, and a limit of
-- the data available here, not a new approximation invented for this
-- fix specifically.
player_points_expected as (
    select
        pp.pg_id,
        pp.pg_gameweek,
        pp.p_position,

        pp.pf_minutes + pp.pf_cs + pp.pf_bonus + pp.pf_saves + pp.pf_pen_saves
            + pp.pf_yellow + pp.pf_red + pp.pf_goals + pp.pf_assists
            + pp.pf_goals_conceded + pp.pf_defcon + pp.pf_own_goals + pp.pf_pen_missed
            as actual_points,

        pp.pf_minutes + pp.pf_bonus + pp.pf_saves + pp.pf_pen_saves
            + pp.pf_yellow + pp.pf_red + pp.pf_defcon + pp.pf_own_goals + pp.pf_pen_missed
            + case pp.p_position
                when 1 then ps.pg_xG * 10
                when 2 then ps.pg_xG * 6
                when 3 then ps.pg_xG * 5
                when 4 then ps.pg_xG * 4
                else 0
              end
            + (ps.pg_xA * 3)
            + case
                when pp.p_position in (1, 2) then -floor(ps.pg_xGa / 2.0)
                else 0
              end
            + case pp.p_position
                when 1 then 4 * exp(-ps.pg_xGa)
                when 2 then 4 * exp(-ps.pg_xGa)
                when 3 then 1 * exp(-ps.pg_xGa)
                else 0
              end
            as expected_points

    from {{ ref('player_points') }} pp
    left join {{ ref('player_stats') }} ps
        on ps.pg_id = pp.pg_id and ps.pg_gameweek = pp.pg_gameweek
),

-- Team-level underlying attacking output: this team's total npxG created
-- per gameweek (summed across every player who took the pitch that
-- match -- each player's own pg_xG is their individual contribution, so
-- summing them recovers the team's match total).
team_gw_attack as (
    select
        p.p_team as team_id,
        ps.pg_gameweek,
        sum(ps.pg_xG) as team_gw_xg
    from {{ ref('player_stats') }} ps
    inner join {{ ref('players') }} p on p.p_id = ps.pg_id
    where ps.pg_minutes > 0
    group by p.p_team, ps.pg_gameweek
),

-- Team-level underlying defensive solidity: this team's xG conceded per
-- gameweek. pg_xGa is a *shared* value across every player from the same
-- team in the same match (it's the team's own conceded expected goals,
-- not a personal figure), so this is averaged rather than summed -- an
-- average recovers the single match value regardless of how many of the
-- team's players happened to feature.
team_gw_defence as (
    select
        p.p_team as team_id,
        ps.pg_gameweek,
        avg(ps.pg_xGa) as team_gw_xga
    from {{ ref('player_stats') }} ps
    inner join {{ ref('players') }} p on p.p_id = ps.pg_id
    where ps.pg_minutes > 0
    group by p.p_team, ps.pg_gameweek
),

-- Round 7.4: team_gw_attack and team_gw_defence combined with a recency
-- weight at ROW level (one row per team per played gameweek), rather
-- than only ever being aggregated straight into team_rates like before
-- -- this is what lets the strength-of-opposition adjustment below
-- subtract out one specific gameweek's contribution later
-- (team_gw_loo_rates), which needs each gameweek's own weighted value on
-- its own, not just the final aggregated rate.
--
-- Round 7.5: this now joins team_strength_decay instead of gw_decay --
-- see TEAM_STRENGTH_DECAY_RATE above for why team-level attack/defence
-- strength needs its own, slower decay than individual player quality
-- shares. Since the strength-of-opposition adjustment (team_gw_loo_rates/
-- team_gw_opponent_difficulty below) is built directly from this same
-- weighted contribution, it inherits the gentler decay too -- correctly
-- so, since it's asking the same "how strong is this team" question,
-- just leave-one-out adjusted.
team_gw_contribution as (
    select
        tga.team_id,
        tga.pg_gameweek as gw_id,
        tsd.weight,
        tga.team_gw_xg,
        coalesce(tgd.team_gw_xga, 0) as team_gw_xga
    from team_gw_attack tga
    inner join team_strength_decay tsd on tsd.gw_id = tga.pg_gameweek
    left join team_gw_defence tgd
        on tgd.team_id = tga.team_id and tgd.pg_gameweek = tga.pg_gameweek
),

-- Recency-weighted average of each team's per-gameweek attack/defence
-- numbers -- "how strong is this team right now", not a flat season
-- average. Unchanged in what it produces (weighted_attack_rate/
-- weighted_defence_rate, used by team_scores exactly as before) --
-- Round 7.4 just aggregates from team_gw_contribution above instead of
-- re-deriving the same join inline, and additionally keeps the raw
-- (un-divided) sums alongside the final rates, because the strength-of-
-- opposition adjustment below needs to subtract one gameweek's
-- contribution back out of these totals (a leave-one-out rate), which
-- isn't possible starting from the already-divided rate alone.
team_rates as (
    select
        team_id,
        sum(weight) as sum_weight,
        sum(team_gw_xg * weight) as sum_weighted_xg,
        sum(team_gw_xga * weight) as sum_weighted_xga,
        sum(team_gw_xg * weight) / nullif(sum(weight), 0) as weighted_attack_rate,
        sum(team_gw_xga * weight) / nullif(sum(weight), 0) as weighted_defence_rate
    from team_gw_contribution
    group by team_id
),

-- Round 8: the league-wide mean/standard deviation of each rate, each as
-- a single row -- computed once here and reused by both team_scores
-- (below) and team_gw_opponent_difficulty (further down, the leave-one-
-- out strength-of-opposition adjustment), so a leave-one-out value gets
-- scored against exactly the same population its full-season counterpart
-- does, and the population itself is worked out only once.
team_rate_population as (
    select
        avg(weighted_attack_rate)    as mean_attack,
        stdev(weighted_attack_rate)  as stddev_attack,
        avg(weighted_defence_rate)   as mean_defence,
        stdev(weighted_defence_rate) as stddev_defence
    from team_rates
),

-- Round 8: both rates turned into 0-10 z-scores across all 20 teams,
-- rather than percentiles -- see the ROUND 8 note at the top of this
-- file. Attack compares each team's rate to the league mean directly (a
-- higher rate is better, so a positive z-score raises the score).
-- Defence flips the sign in the z-score itself (a LOWER xG-conceded rate
-- is better, so a team a standard deviation below the mean should score
-- ABOVE 5, not below it) rather than needing a separate "order by desc"
-- convention the way percent_rank did.
--
-- Round 13: also expose the RAW, unmapped z-scores (team_attack_z/
-- team_defence_z -- in standard-deviation units, not yet stretched onto
-- 0-10) alongside the usual 0-10 scores. player_team_strength (a
-- player's own single team) only ever needs the 0-10 scores below, but
-- team_fixture_raw_z (a team's next 5 DIFFERENT opponents, further
-- down) needs the raw z's instead -- see the Round 13 note on
-- team_fixture_outlook further down for why fixture_outlook_score was
-- quietly compressed towards 5, and why this is the fix.
team_scores as (
    select
        tr.team_id,
        (tr.weighted_attack_rate - trp.mean_attack) / nullif(trp.stddev_attack, 0)
            as team_attack_z,
        (trp.mean_defence - tr.weighted_defence_rate) / nullif(trp.stddev_defence, 0)
            as team_defence_z,
        {{ zscore_to_10('tr.weighted_attack_rate', 'trp.mean_attack', 'trp.stddev_attack', SCORE_SD_SPAN) }} as team_attack_score,
        {{ zscore_to_10('trp.mean_defence - tr.weighted_defence_rate', '0', 'trp.stddev_defence', SCORE_SD_SPAN) }} as team_defence_score
    from team_rates tr
    cross join team_rate_population trp
),

-- Round 7.4: the position-based attack/defence blend share (previously
-- computed inline, identically, three separate times below) is now its
-- own small CTE, so the strength-of-opposition adjustment further down
-- can reuse the exact same per-position lean without a fourth copy of
-- the same CASE expression. player_team_strength looks this up by
-- player; team_fixture_raw_z (Round 13, further down) needs the same
-- 4 position values but at the team level, so it uses its own small
-- position_attack_share lookup instead of joining through a player row.
player_attack_share as (
    select
        p_id,
        case p_position
            when 1 then {{ GK_TEAM_ATTACK_SHARE }}
            when 2 then {{ DEF_TEAM_ATTACK_SHARE }}
            when 3 then {{ MID_TEAM_ATTACK_SHARE }}
            when 4 then {{ FWD_TEAM_ATTACK_SHARE }}
        end as attack_share
    from {{ ref('players') }}
),

-- Each player's own team's attack/defence scores, plus the position-
-- specific blend of the two into one team_strength_score. attack_share
-- is how much of that blend leans on attack vs defence for this position
-- (see player_attack_share above and the *_TEAM_ATTACK_SHARE tunables).
--
-- Missing data (e.g. gameweek 1, before any fixture has been played and
-- percent_rank() has nothing to rank yet) defaults to 5, the neutral
-- midpoint of the 0-10 scale, rather than 0 -- team_scores is empty for
-- every team equally in that situation, so defaulting to 0 would simply
-- (and wrongly) mark every team as the worst possible team, dragging
-- every player's star down uniformly until the season's first results
-- are in. 5 keeps this ingredient neutral instead of penalising.
player_team_strength as (
    select
        p.p_id,
        coalesce(ts.team_attack_score, 5) as team_attack_score,
        coalesce(ts.team_defence_score, 5) as team_defence_score,
        pas.attack_share,
        (coalesce(ts.team_attack_score, 5) * pas.attack_share)
        + (coalesce(ts.team_defence_score, 5) * (1 - pas.attack_share))
            as team_strength_score
    from {{ ref('players') }} p
    inner join player_attack_share pas on pas.p_id = p.p_id
    left join team_scores ts on ts.team_id = p.p_team
),

-- Round 7.4: for every team and every one of its own played gameweeks,
-- what its attack/defence rate would have been EXCLUDING that specific
-- gameweek -- i.e. subtracting that one match's own weighted
-- contribution back out of the team's season totals above. This is what
-- makes the opposition-strength adjustment below leave-one-out: when
-- grading how tough Coventry were in the specific match an Arsenal
-- player faced them, Coventry's own numbers from THAT match are
-- excluded from what "how tough is Coventry" means for judging it --
-- otherwise a single freak scoreline would partly be marking its own
-- homework (a heavy Coventry defensive concession in that match would
-- both make the scoring player's raw numbers look better AND drag down
-- the very "how strong was this defence" figure used to grade that same
-- performance). A different gameweek for the same team excludes a
-- different match, so e.g. Coventry's effective strength when grading
-- an Arsenal player is not the same number used to grade a Brighton
-- player, even though both played Coventry.
team_gw_loo_rates as (
    select
        tgc.team_id,
        tgc.gw_id,
        (tr.sum_weighted_xg - (tgc.team_gw_xg * tgc.weight))
            / nullif(tr.sum_weight - tgc.weight, 0) as loo_attack_rate,
        (tr.sum_weighted_xga - (tgc.team_gw_xga * tgc.weight))
            / nullif(tr.sum_weight - tgc.weight, 0) as loo_defence_rate
    from team_gw_contribution tgc
    inner join team_rates tr on tr.team_id = tgc.team_id
),

-- Round 8: turns each leave-one-out rate into the same 0-10 z-score scale
-- team_scores uses, against exactly the same population (team_rate_
-- population above) -- i.e. "if this were this team's season-long rate,
-- how many standard deviations from the league average would it be".
-- Much more direct than the old percent_rank-equivalent "count how many
-- teams this beats" approach, since a z-score against a fixed population
-- is just arithmetic against that population's mean/standard deviation --
-- no window function, no cross join against all 20 teams' rows, no
-- group by. Same direction convention as team_scores: attack scores
-- straight off the mean (higher is better), defence flips the sign in
-- the z-score itself (a lower xG-conceded rate is better).
-- The outer CASE still matters for correctness: when l.loo_attack_rate/
-- loo_defence_rate is NULL (not enough history yet for this team to
-- leave one gameweek out of -- see team_gw_loo_rates above), this must
-- stay NULL rather than resolve to some real number, so it can correctly
-- default to the neutral 5 further down in player_gw_opponent_score
-- instead of quietly marking an under-sampled opponent as average (or
-- worse) by accident.
team_gw_opponent_difficulty as (
    select
        l.team_id,
        l.gw_id,
        case when l.loo_attack_rate is null then null else
            {{ zscore_to_10('l.loo_attack_rate', 'trp.mean_attack', 'trp.stddev_attack', SCORE_SD_SPAN) }}
        end as loo_attack_score,
        case when l.loo_defence_rate is null then null else
            {{ zscore_to_10('trp.mean_defence - l.loo_defence_rate', '0', 'trp.stddev_defence', SCORE_SD_SPAN) }}
        end as loo_defence_score
    from team_gw_loo_rates l
    cross join team_rate_population trp
),

-- Same shape as team_upcoming_fixtures below, but for gameweeks already
-- PLAYED (joined to gw_decay instead of next5) -- this is what lets a
-- past match be matched back to its opponent for the strength-of-
-- opposition adjustment below. Built as the same explicit UNION ALL of
-- the home leg and away leg, for the same reason: avoids the OR-based
-- join bug documented on team_upcoming_fixtures and get_next_5/
-- get_team_fixtures elsewhere in this project.
team_played_fixtures as (
    select
        f_home_team as team_id,
        f_away_team as opponent_id,
        gd.gw_id
    from {{ ref('fixtures') }} f
    inner join gw_decay gd on f.f_gameweek = gd.gw_id

    union all

    select
        f_away_team as team_id,
        f_home_team as opponent_id,
        gd.gw_id
    from {{ ref('fixtures') }} f
    inner join gw_decay gd on f.f_gameweek = gd.gw_id
),

-- Round 7.4: each player's own team's opponent, gameweek by gameweek,
-- graded from this player's own position-specific point of view -- the
-- exact same attack_share blend used for team_strength_score/fixture_
-- outlook_score above (how strong was the opponent's defence, if this
-- player's own output leans on their team's attack; how strong was the
-- opponent's attack, if it leans on their team's defence), just applied
-- to the opponent actually faced in a specific past gameweek instead of
-- this player's own team, and using the leave-one-out score instead of
-- the plain team_scores figure. Missing data (a gameweek with no
-- resolvable opponent/loo figure -- e.g. very early in a team's own
-- season, before there's enough history to leave one match out of)
-- defaults to 5, the neutral midpoint, for the same reason
-- player_team_strength defaults missing team_scores to 5 above.
player_gw_opponent_score as (
    select
        p.p_id,
        tpf.gw_id,
        coalesce(
            (pas.attack_share * cod.loo_defence_score)
            + ((1 - pas.attack_share) * cod.loo_attack_score),
            5
        ) as opponent_difficulty_score
    from {{ ref('players') }} p
    inner join player_attack_share pas on pas.p_id = p.p_id
    inner join team_played_fixtures tpf on tpf.team_id = p.p_team
    left join team_gw_opponent_difficulty cod
        on cod.team_id = tpf.opponent_id and cod.gw_id = tpf.gw_id
),

-- The 0-10 difficulty score above turned into a multiplier centred on
-- 1.0 -- see SOS_STRENGTH_FACTOR above for the tunable. A dead-average
-- opponent (score 5) leaves a performance completely unchanged; the
-- toughest opponent that gameweek scales it up, the weakest scales it
-- down, linearly in between.
player_gw_opponent_multiplier as (
    select
        p_id,
        gw_id,
        opponent_difficulty_score,
        1.0 + {{ SOS_STRENGTH_FACTOR }} * (opponent_difficulty_score - 5) / 5.0
            as opponent_multiplier
    from player_gw_opponent_score
),

-- One row per player-gameweek, with the recency weight attached and the
-- weighted contributions pre-multiplied -- summing these per player
-- below gives a recency-weighted total in one pass, rather than
-- recomputing the weighting logic per aggregate.
--
-- Round 7.4: actual/expected points are now ALSO scaled by that specific
-- gameweek's opponent-difficulty multiplier (player_gw_opponent_
-- multiplier above) before being weighted for recency -- so a big
-- performance against a tough opponent counts for more than the same
-- numbers against a weak one, and both still fade with recency exactly
-- as before. Deliberately only actual/expected points -- NOT w_minutes
-- or w_defcons -- this only touches "quality", per the request that
-- prompted it; minutes-security and defensive-contribution rate are
-- unrelated to how hard the opponent was.
player_gw_weighted as (
    select
        ppe.pg_id,
        ppe.p_position,
        gd.weight,
        gd.weight * ps.pg_minutes       as w_minutes,
        gd.weight * coalesce(pgom.opponent_multiplier, 1.0) * ppe.actual_points
            as w_actual_points,
        gd.weight * coalesce(pgom.opponent_multiplier, 1.0) * ppe.expected_points
            as w_expected_points,
        gd.weight * ps.pg_defcons       as w_defcons,
        ps.pg_minutes,
        ps.pg_defcons
    from player_points_expected ppe
    inner join gw_decay gd on gd.gw_id = ppe.pg_gameweek
    left join player_gw_opponent_multiplier pgom
        on pgom.p_id = ppe.pg_id and pgom.gw_id = ppe.pg_gameweek
    left join {{ ref('player_stats') }} ps
        on ps.pg_id = ppe.pg_id and ps.pg_gameweek = ppe.pg_gameweek
),

-- One row per player: recency-weighted per-90 rates for actual points,
-- expected points and defensive-contribution actions, each gated by
-- MIN_MINUTES_FOR_FORM_RATE so a player with barely any minutes doesn't
-- get an inflated small-sample rate. The gate uses total (unweighted)
-- minutes played this season -- decay already handles "how much should
-- old data count", this is purely a sample-size floor.
quality_rates as (
    select
        p.p_id,
        p.p_full_name as player,
        p.p_position,

        sum(pgw.pg_minutes) as season_minutes,

        case
            when sum(pgw.pg_minutes) < {{ MIN_MINUTES_FOR_FORM_RATE }} then 0
            else sum(pgw.w_actual_points) * 90.0 / nullif(sum(pgw.w_minutes), 0)
        end as actual_p90,

        case
            when sum(pgw.pg_minutes) < {{ MIN_MINUTES_FOR_FORM_RATE }} then 0
            else sum(pgw.w_expected_points) * 90.0 / nullif(sum(pgw.w_minutes), 0)
        end as expected_p90,

        case
            when sum(pgw.pg_minutes) < {{ MIN_MINUTES_FOR_FORM_RATE }} then 0
            else sum(pgw.w_defcons) * 90.0 / nullif(sum(pgw.w_minutes), 0)
        end as defcon_p90

    from {{ ref('players') }} p
    left join player_gw_weighted pgw on pgw.pg_id = p.p_id
    group by p.p_id, p.p_full_name, p.p_position
),

-- Round 8: three independent 0-10 z-scores (not percentiles any more --
-- see the ROUND 8 note at the top of this file), each computed *within
-- position* and only against players who actually have a non-zero rate
-- -- players with nothing to show yet default to 0 rather than being
-- counted into the mean/standard deviation everyone else is being
-- measured against.
quality_actual_percentiles as (
    select
        p_id,
        {{ zscore_to_10('actual_p90', 'mean_actual', 'stddev_actual', SCORE_SD_SPAN) }} as score
    from (
        select
            p_id,
            actual_p90,
            avg(actual_p90) over (partition by p_position)   as mean_actual,
            stdev(actual_p90) over (partition by p_position) as stddev_actual
        from quality_rates
        where actual_p90 > 0
    ) x
),

quality_expected_percentiles as (
    select
        p_id,
        {{ zscore_to_10('expected_p90', 'mean_expected', 'stddev_expected', SCORE_SD_SPAN) }} as score
    from (
        select
            p_id,
            expected_p90,
            avg(expected_p90) over (partition by p_position)   as mean_expected,
            stdev(expected_p90) over (partition by p_position) as stddev_expected
        from quality_rates
        where expected_p90 > 0
    ) x
),

defcon_percentiles as (
    select
        p_id,
        {{ zscore_to_10('defcon_p90', 'mean_defcon', 'stddev_defcon', SCORE_SD_SPAN) }} as score
    from (
        select
            p_id,
            defcon_p90,
            avg(defcon_p90) over (partition by p_position)   as mean_defcon,
            stdev(defcon_p90) over (partition by p_position) as stddev_defcon
        from quality_rates
        where defcon_p90 > 0
    ) x
),

-- The player's team's next 5 fixtures, one row per (team, upcoming
-- fixture), carrying the opponent's team_id and the fixture's proximity
-- weight -- built as an explicit UNION ALL of the home leg and away leg
-- (the same shape the previous model used for its team CTEs), which
-- avoids the OR-based join bug documented in get_next_5/get_team_fixtures
-- elsewhere in this project.
team_upcoming_fixtures as (
    select
        f_home_team as team_id,
        f_away_team as opponent_id,
        next5.weight
    from {{ ref('fixtures') }} f
    inner join next5 on f.f_gameweek = next5.gw_id

    union all

    select
        f_away_team as team_id,
        f_home_team as opponent_id,
        next5.weight
    from {{ ref('fixtures') }} f
    inner join next5 on f.f_gameweek = next5.gw_id
),

-- Round 13: the 4 positions' TEAM_ATTACK_SHARE values, as their own
-- small lookup rather than joined in via player_attack_share -- team_
-- fixture_raw_z below needs "every position's version of this team's
-- blended fixture favourability", not any one specific player's, so it
-- cross-joins this directly instead of going through a player row.
position_attack_share as (
    select 1 as p_position, {{ GK_TEAM_ATTACK_SHARE }} as attack_share
    union all select 2, {{ DEF_TEAM_ATTACK_SHARE }}
    union all select 3, {{ MID_TEAM_ATTACK_SHARE }}
    union all select 4, {{ FWD_TEAM_ATTACK_SHARE }}
),

-- Round 13: each team's OWN blended fixture favourability across its
-- own next 5 opponents, computed once per (team, position) rather than
-- per player -- fixture_outlook_score was always identical for every
-- player sharing a team and position anyway (attack_share only depends
-- on position), this just computes it at that natural grain directly.
-- Still in raw z-score units (standard deviations, sign-flipped so
-- higher is always more favourable) -- deliberately NOT mapped onto
-- 0-10 yet, weighted by proximity exactly as fixture_outlook_score
-- always was. See the note on team_fixture_outlook below for why the
-- 0-10 mapping has to wait until after this.
team_fixture_raw_z as (
    select
        tuf.team_id,
        pas.p_position,
        sum(
            ((pas.attack_share * -coalesce(ots.team_defence_z, 0))
            + ((1 - pas.attack_share) * -coalesce(ots.team_attack_z, 0)))
            * tuf.weight
        ) / nullif(sum(tuf.weight), 0) as blended_favourability_z
    from team_upcoming_fixtures tuf
    cross join position_attack_share pas
    left join team_scores ots on ots.team_id = tuf.opponent_id
    group by tuf.team_id, pas.p_position, pas.attack_share
),

-- Round 13: the league-wide mean/standard deviation of EVERY team's own
-- blended-next-5 figure above, computed separately within each position
-- (since attack_share -- and so the blend itself -- differs by
-- position, a goalkeeper's population of "how good do the next 5
-- fixtures look" is not the same population a forward's belongs to).
-- This is what team_fixture_outlook below z-scores each team's own
-- figure against, instead of reusing team_rate_population (built for
-- single-team strength, a different quantity with a different natural
-- spread).
team_fixture_population as (
    select
        p_position,
        avg(blended_favourability_z) as mean_blend,
        stdev(blended_favourability_z) as stddev_blend
    from team_fixture_raw_z
    group by p_position
),

-- Round 13 fix, the actual root cause of fixture_outlook_score looking
-- "squeezed" (everyone landing around 5-6 regardless of how genuinely
-- easy or hard their next 5 games actually were, even after the next5
-- fix above, which only stopped it including MORE than 5 fixtures and
-- didn't touch this separate issue): averaging together 5 DIFFERENT
-- opponents' z-scores -- each one itself a draw from the same
-- team_rate_population used to rate a team's own single-team strength
-- -- mechanically shrinks the spread of that average, a standard
-- statistical fact about averaging several samples from one population
-- (roughly by the square root of how many you're averaging, so close to
-- half the spread for 5 fixtures). Re-mapping that already-narrower
-- average back onto 0-10 using the SAME span calibrated for a single
-- team's full-season rate (as an earlier attempt at this fix did) still
-- comes out compressed, because the span itself was never the problem
-- -- the population being measured against was. A team's blended-next-
-- 5-opponents figure and a team's own single-season rate are two
-- genuinely different quantities with two different natural spreads,
-- and each needs to be judged against a population of ITS OWN kind.
--
-- Fixed by z-scoring team_fixture_raw_z's blended figure against team_
-- fixture_population above (every team's OWN blended-next-5 figure,
-- within the same position) instead of against team_rate_population --
-- comparing each team's run of fixtures to how favourable other teams'
-- OWN next-5 runs are, which is the actual comparison "how good does
-- this fixture list look" is supposed to be making.
team_fixture_outlook as (
    select
        tfz.team_id,
        tfz.p_position,
        {{ zscore_to_10(
            'tfz.blended_favourability_z', 'tfp.mean_blend', 'tfp.stddev_blend', SCORE_SD_SPAN
        ) }} as fixture_outlook_score
    from team_fixture_raw_z tfz
    inner join team_fixture_population tfp on tfp.p_position = tfz.p_position
),

-- Per-player lookup of the above by (team, position) -- kept as its own
-- small CTE (rather than joining team_fixture_outlook directly into
-- component_scores) so component_scores doesn't need to know anything
-- about how fixture_outlook_score is actually computed, same as before.
fixture_outlook as (
    select
        p.p_id,
        tfo.fixture_outlook_score
    from {{ ref('players') }} p
    inner join team_fixture_outlook tfo
        on tfo.team_id = p.p_team and tfo.p_position = p.p_position
),

-- Minutes-security gate: how much to trust this player's rating at all,
-- given how nailed-on they've recently been and whether there's a live
-- news/injury flag against them.
--
-- Round 7.3: this used to average minutes flatly across the last 5
-- gameweeks (every gameweek in the window counted equally). That meant
-- a player who'd been out injured, then returned and started playing
-- full minutes again, stayed penalised for a month by the injury-
-- affected gap sitting equally-weighted alongside their fresh
-- appearances -- exactly the "Van Ewijk was flagged before one game,
-- missed it, and shouldn't still be marked down for it once he's back"
-- case raised in feedback.
--
-- What this project's data genuinely can't do is look up *why* a
-- gameweek was missed after the fact: p_news/p_news_date (see below)
-- only ever holds the LATEST news snapshot from the FPL API -- nothing
-- in the raw extraction retains what a player's news flag said in a
-- past gameweek, so there's no way to specifically say "gameweek 6 was
-- an injury absence, discount it" once gameweek 7 has arrived. Building
-- that properly would mean snapshotting p_news/p_news_date into its own
-- history table on every extraction run, keyed by gameweek -- a
-- pipeline change, not something this model can conjure from data that
-- was never kept.
--
-- What it CAN do, without new data: weight the last 5 gameweeks by
-- recency (minutes_decay above) instead of averaging them flatly, with
-- its own much steeper decay than gw_decay's -- fitness/selection
-- status is a fast-changing "is this true right now" signal (a player
-- can go from out-injured to back-starting within a single gameweek),
-- unlike underlying quality, which genuinely reflects a longer trend.
-- With a steep decay, the very latest gameweek dominates the
-- reliability read, so a player who's just returned and started
-- recovers towards a trustworthy score within a game or two, rather
-- than an old injury gap dragging a flat average down for another
-- month after they're already back. It doesn't identify the absence as
-- an injury specifically (nothing here does) -- it just stops
-- penalising a RECOVERED, currently-playing player for something that's
-- clearly behind them, whatever the reason was.
minutes_security_inputs as (
    select
        p.p_id,
        sum(coalesce(ps.pg_minutes, 0) * md.weight) as weighted_minutes,
        sum({{ MINUTES_PER_MATCH }} * md.weight) as weighted_capacity
    from {{ ref('players') }} p
    cross join minutes_decay md
    left join {{ ref('player_stats') }} ps
        on ps.pg_id = p.p_id and ps.pg_gameweek = md.gw_id
    group by p.p_id
),

minutes_security as (
    select
        msi.p_id,
        case
            when msi.weighted_minutes >= msi.weighted_capacity then 1.0
            else {{ MINUTES_SECURITY_FLOOR }}
                + (1.0 - {{ MINUTES_SECURITY_FLOOR }})
                * (msi.weighted_minutes / nullif(msi.weighted_capacity, 0))
        end
        *
        -- p_news_date (raw_players.news_added) is stored as text, not a
        -- native datetime column -- the FPL API returns it as an ISO-8601
        -- string with a trailing "Z", which SQL Server's implicit
        -- string->datetime conversion can't parse. try_convert(..., 127)
        -- parses that exact ISO-8601 format explicitly and returns NULL
        -- instead of erroring for anything it can't parse. This part is
        -- about the CURRENT flag only (unchanged from before) -- when a
        -- flag clears, this multiplier reverts to 1.0 on its own; it's
        -- the weighted-minutes ratio above that now also stops holding
        -- a cleared flag's past absence against a recovered player.
        case
            when pl.p_news is not null and pl.p_news <> ''
                 and try_convert(datetime2, pl.p_news_date, 127) is not null
                 and try_convert(datetime2, pl.p_news_date, 127) >= dateadd(day, -{{ NEWS_LOOKBACK_DAYS }}, getdate())
            then {{ INJURY_NEWS_MULTIPLIER }}
            else 1.0
        end as minutes_security_score
    from minutes_security_inputs msi
    left join {{ ref('players') }} pl on pl.p_id = msi.p_id
),

-- The four 0-10 ingredients, computed once each so later steps don't
-- need to repeat any of this arithmetic -- plus each ingredient's actual
-- weight for this specific player. Team-strength/fixtures weights are
-- still a straight lookup by position, but quality_weight/defcon_weight
-- are not purely position-based any more -- see MID_DEFCON_ROLE_THRESHOLD
-- and (Round 10) DEF_DEFCON_ROLE_THRESHOLD above: a defender or
-- midfielder whose own recency-weighted defcon_p90 sits below their
-- position's threshold gets a defcon_weight of 0, with that same slice
-- added onto their quality_weight instead, so the two still sum to
-- DEF_WEIGHT_QUALITY + DEF_WEIGHT_DEFCON (or the midfielder
-- equivalent) for every player either way -- goalkeepers and forwards
-- are unaffected, since defcon_weight is a flat 0 for both regardless
-- of role.
component_scores as (
    select
        qr.p_id,
        qr.player,
        qr.p_position,

        -- Round 8: the raw per-90 rates behind quality_actual_score/
        -- quality_expected_score (an actual points-per-90 NUMBER, not a
        -- 0-10 score) carried straight through to the final output as
        -- actual_points_p90/expected_points_p90 -- not used anywhere in
        -- this model itself, but needed by player_expected_points.sql
        -- (the new next-5-fixtures expected-points model) so it can reuse
        -- this model's already-computed recency-weighted quality rate
        -- instead of recomputing gw_decay/quality_rates a second time.
        round(qr.actual_p90, 3) as actual_points_p90,
        round(qr.expected_p90, 3) as expected_points_p90,

        round(coalesce(qap.score, 0), 2) as quality_actual_score,
        round(coalesce(qep.score, 0), 2) as quality_expected_score,
        (coalesce(qap.score, 0) * {{ QUALITY_ACTUAL_WEIGHT }})
            + (coalesce(qep.score, 0) * {{ QUALITY_EXPECTED_WEIGHT }})
            as quality_score,

        round(coalesce(dcp.score, 0), 2) as defensive_contribution_score,

        round(pts.team_attack_score, 2) as team_attack_score,
        round(pts.team_defence_score, 2) as team_defence_score,
        round(pts.team_strength_score, 2) as team_strength_score,

        -- Fixture outlook is already a weighted average of numbers each
        -- individually in [0, 10], so it can't itself fall outside that
        -- range -- no clamp needed, unlike the old model's linear rescale
        -- of a raw 1-5 difficulty number.
        round(coalesce(fo.fixture_outlook_score, 5), 2) as fixture_outlook_score,

        round(coalesce(ms.minutes_security_score, 1.0), 2) as minutes_security_score,

        case
            when qr.p_position = 1 then {{ GK_WEIGHT_DEFCON }}
            when qr.p_position = 2 and coalesce(qr.defcon_p90, 0) >= {{ DEF_DEFCON_ROLE_THRESHOLD }}
                then {{ DEF_WEIGHT_DEFCON }}
            -- Attacking wing-back/ball-playing centre-back pushed
            -- forward (defcon_p90 below the threshold, or no minutes to
            -- judge it from yet): this ingredient isn't a realistic
            -- scoring route for them, so its weight is 0 -- same logic
            -- as the midfielder case below, just at the defender-
            -- specific threshold (see DEF_DEFCON_ROLE_THRESHOLD above).
            when qr.p_position = 2 then 0
            when qr.p_position = 3 and coalesce(qr.defcon_p90, 0) >= {{ MID_DEFCON_ROLE_THRESHOLD }}
                then {{ MID_WEIGHT_DEFCON }}
            -- Attacking midfielder (defcon_p90 below the threshold, or
            -- no minutes to judge it from yet): this ingredient isn't a
            -- realistic scoring route for them, so its weight is 0.
            when qr.p_position = 3 then 0
            when qr.p_position = 4 then {{ FWD_WEIGHT_DEFCON }}
        end as defcon_weight,

        case
            when qr.p_position = 1 then {{ GK_WEIGHT_QUALITY }}
            when qr.p_position = 2 and coalesce(qr.defcon_p90, 0) >= {{ DEF_DEFCON_ROLE_THRESHOLD }}
                then {{ DEF_WEIGHT_QUALITY }}
            -- The weight defcon_weight didn't get above is added on
            -- here instead, so this player's four weights still sum to
            -- 1.0 -- just redistributed between the two ingredients
            -- rather than genuinely dropped. Same pattern as the
            -- midfielder case below.
            when qr.p_position = 2 then {{ DEF_WEIGHT_QUALITY }} + {{ DEF_WEIGHT_DEFCON }}
            when qr.p_position = 3 and coalesce(qr.defcon_p90, 0) >= {{ MID_DEFCON_ROLE_THRESHOLD }}
                then {{ MID_WEIGHT_QUALITY }}
            when qr.p_position = 3 then {{ MID_WEIGHT_QUALITY }} + {{ MID_WEIGHT_DEFCON }}
            when qr.p_position = 4 then {{ FWD_WEIGHT_QUALITY }}
        end as quality_weight,

        case qr.p_position
            when 1 then {{ GK_WEIGHT_TEAM_STRENGTH }}
            when 2 then {{ DEF_WEIGHT_TEAM_STRENGTH }}
            when 3 then {{ MID_WEIGHT_TEAM_STRENGTH }}
            when 4 then {{ FWD_WEIGHT_TEAM_STRENGTH }}
        end as team_strength_weight,

        case qr.p_position
            when 1 then {{ GK_WEIGHT_FIXTURES }}
            when 2 then {{ DEF_WEIGHT_FIXTURES }}
            when 3 then {{ MID_WEIGHT_FIXTURES }}
            when 4 then {{ FWD_WEIGHT_FIXTURES }}
        end as fixtures_weight

    from quality_rates qr
    left join quality_actual_percentiles   qap on qap.p_id = qr.p_id
    left join quality_expected_percentiles qep on qep.p_id = qr.p_id
    left join defcon_percentiles           dcp on dcp.p_id = qr.p_id
    left join player_team_strength         pts on pts.p_id = qr.p_id
    left join fixture_outlook              fo  on fo.p_id = qr.p_id
    left join minutes_security             ms  on ms.p_id = qr.p_id
),

-- The blended score: the four weighted ingredients above (each already
-- 0-10, and each player's four weights summing to 1.0). Deliberately
-- NOT yet scaled by the minutes-security gate -- see the Round 7.2 note
-- below for why that has to happen after the percentile rescale, not
-- before it. The case is a defensive clamp in case the weights above are
-- retuned to no longer sum to exactly 1.0.
blend_scores as (
    select
        p_id,
        player,
        p_position,
        actual_points_p90,
        expected_points_p90,
        quality_actual_score,
        quality_expected_score,
        quality_score,
        defensive_contribution_score,
        team_attack_score,
        team_defence_score,
        team_strength_score,
        fixture_outlook_score,
        minutes_security_score,
        quality_weight,
        defcon_weight,
        team_strength_weight,
        fixtures_weight,
        case
            when (
                (quality_score * quality_weight)
                + (defensive_contribution_score * defcon_weight)
                + (team_strength_score * team_strength_weight)
                + (fixture_outlook_score * fixtures_weight)
            ) > 10 then 10
            when (
                (quality_score * quality_weight)
                + (defensive_contribution_score * defcon_weight)
                + (team_strength_score * team_strength_weight)
                + (fixture_outlook_score * fixtures_weight)
            ) < 0 then 0
            else (
                (quality_score * quality_weight)
                + (defensive_contribution_score * defcon_weight)
                + (team_strength_score * team_strength_weight)
                + (fixture_outlook_score * fixtures_weight)
            )
        end as blend_score
    from component_scores
)

-- Round 8: the Round 7.1/7.2 percentile rescale of blend_score
-- (formerly "underlying_scores", now removed) is gone -- reverted, as
-- asked, back to blend_score itself being the headline score before the
-- minutes-security gate. See the ROUND 8 note at the top of this file
-- for the full reasoning and the honest trade-off it brings back: this
-- is an average of four only loosely-correlated ingredients, so it will
-- generally sit a bit below whichever ingredient a player is individually
-- best at, not equal to it -- reaching 9-10 now means being genuinely
-- good across most of the blend, not just brilliant on one axis. The
-- z-score ingredient scores above make that noticeably more reachable
-- than percentiles did (several genuinely elite players can now all
-- score close to 10 on quality itself, rather than only the outright
-- #1 in the whole position), but it's a real blend, not a rebadge of
-- quality_score alone.
--
-- The minutes-security gate is still applied AFTER blend_score, exactly
-- as Round 7.2 fixed it to be (see that round's note, still accurate --
-- the gate needs to scale a clean, un-rescaled "how good are this
-- player's underlying signals" number, not something that's already been
-- run through a second normalisation step on top of it).
select
    p_id,
    player,
    p_position,

    actual_points_p90,
    expected_points_p90,

    quality_actual_score,
    quality_expected_score,
    round(quality_score, 2) as quality_score,
    round(quality_weight, 2) as quality_weight,

    defensive_contribution_score,
    round(defcon_weight, 2) as defcon_weight,

    team_attack_score,
    team_defence_score,
    round(team_strength_score, 2) as team_strength_score,
    round(team_strength_weight, 2) as team_strength_weight,

    fixture_outlook_score,
    round(fixtures_weight, 2) as fixtures_weight,

    minutes_security_score,

    -- Final star: blend_score (already clamped to 0-10 above) scaled
    -- down by the minutes-security gate. Naturally still within 0-10
    -- with no further clamp needed -- blend_score is at most 10,
    -- minutes_security_score is at most 1.0, so their product can't
    -- exceed 10, and both are at least 0.
    round(blend_score * minutes_security_score, 2) as star

from blend_scores
