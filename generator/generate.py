"""
Sourcewise synthetic GTM world generator.

Simulates a fictional B2B SaaS company (see config/world.yml) day by day and writes
raw exports shaped like the real tools: HubSpot, GA4, LinkedIn Ads, Google Ads,
Smartlead, Clay, the Reply Bot, the Voice Agent and Stripe.

Design notes
------------
* Deterministic: each simulated day draws its random numbers from rng([seed, day]).
  Extending end_date adds days without changing history, so nightly runs are stable.
* Common random numbers: every day draws the same fixed block of uniforms whatever the
  state, so switching a channel off changes only what that channel caused.
* Planted ground truth: after the real run, the world is re-simulated once per channel
  with that channel switched off. The drop in won revenue is that channel's true
  incremental revenue. It is written to data/truth/, which the dbt models never read
  except in the final evaluation mart.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import math
import os
from collections import defaultdict

import numpy as np
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHANNELS = [
    "linkedin_ads", "google_ads", "retargeting_ads", "organic_search", "direct",
    "referral", "cold_email", "signal_engine", "reply_bot", "voice_agent",
]
NU = 34  # uniforms drawn per person per day (fixed, for common random numbers)

FIRST = ("Aarav Maya Liam Priya Noah Emma Ravi Sofia Ethan Ananya Lucas Chloe Arjun Grace Mateo Zoe "
         "Daniel Isha Owen Hannah Kabir Leah Samuel Nora Vikram Ruby Elias Tara Julian Meera Felix Ava "
         "Rohan Clara Adam Sara Leo Naomi Kiran Ivy").split()
LAST = ("Shah Patel Miller Garcia Chen Kim Rossi Singh Novak Berg Walsh Iyer Costa Park Evans Moreau "
        "Kapoor Haas Duarte Lindqvist Okafor Reyes Brennan Varga Mehta Sato Ferreira Klein Das Holt").split()
TITLES = ["General Counsel", "Head of Legal Ops", "VP Operations", "Legal Operations Manager",
          "Contract Manager", "COO", "Procurement Lead", "Senior Counsel", "Director of Finance Ops",
          "RevOps Manager"]
INDUSTRIES = ["SaaS", "Fintech", "Healthcare", "Logistics", "Manufacturing", "E-commerce",
              "Professional Services", "Insurance"]
ICP_INDUSTRIES = {"SaaS", "Fintech", "Insurance", "Healthcare"}
SYL = "nor vex lum ari tel qua zen bry cor mav oda pix ster ven kal ro tri sol hal ume dex ora lin fab".split()
SUFFIX = ["Labs", "Systems", "Health", "Logistics", "Pay", "Works", "Group", "Cloud", "Freight", "Insure"]
POSTS = [f"https://www.linkedin.com/posts/quillstack-post-{i:03d}" for i in range(1, 41)]
DEAL_STAGES = ["appointmentscheduled", "qualifiedtobuy", "presentationscheduled",
               "decisionmakerboughtin", "contractsent"]


# --------------------------------------------------------------------------- world
class World:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        rng = np.random.default_rng([cfg["seed"], 10**6])
        A = cfg["accounts"]
        self.A = A
        names, domains = set(), []
        self.acct_name, self.acct_domain = [], []
        while len(self.acct_name) < A:
            n = (rng.choice(SYL) + rng.choice(SYL)).capitalize() + " " + rng.choice(SUFFIX)
            if n in names:
                continue
            names.add(n)
            self.acct_name.append(n)
            self.acct_domain.append(n.lower().replace(" ", "") + ".com")
        self.industry = rng.choice(INDUSTRIES, A)
        self.employees = np.round(np.exp(rng.normal(math.log(260), 0.9, A))).astype(int).clip(15, 5000)
        size_fit = np.where((self.employees >= 100) & (self.employees <= 2000), 1.0, 0.55)
        ind_fit = np.array([1.0 if i in ICP_INDUSTRIES else 0.6 for i in self.industry])
        self.fit = (size_fit * ind_fit * rng.uniform(0.8, 1.2, A)).clip(0.3, 1.2)

        lo, hi = cfg["contacts_per_account"]
        counts = rng.integers(lo, hi + 1, A)
        self.acct_of = np.repeat(np.arange(A), counts)
        P = len(self.acct_of)
        self.P = P
        self.first = rng.choice(FIRST, P)
        self.last = rng.choice(LAST, P)
        self.title = rng.choice(TITLES, P)
        self.email = []
        seen = set()
        for p in range(P):
            base = f"{self.first[p].lower()}.{self.last[p].lower()}"
            e, k = f"{base}@{self.acct_domain[self.acct_of[p]]}", 2
            while e in seen:
                e, k = f"{base}{k}@{self.acct_domain[self.acct_of[p]]}", k + 1
            seen.add(e)
            self.email.append(e)
        area = rng.integers(200, 990, P)
        line = rng.integers(0, 10000, P)
        self.phone_digits = [f"{a}555{l:04d}" for a, l in zip(area, line)]
        self.two_devices = rng.random(P) < cfg["second_device_share"]
        self.dup = rng.random(P) < cfg["personal_email_dup_share"]
        self.client_ids = [
            [f"{rng.integers(10**9, 2 * 10**9)}.{rng.integers(1_600_000_000, 1_700_000_000)}"
             for _ in range(2 if self.two_devices[p] else 1)]
            for p in range(P)
        ]


def size_band(emp: int) -> str:
    return "small" if emp < 100 else ("mid" if emp <= 1000 else "large")


# ----------------------------------------------------------------------- recorder
class Recorder:
    """Collects raw export rows during the real (non-counterfactual) run."""

    def __init__(self):
        self.rows = defaultdict(list)
        self.first_identified = {}   # person -> (day, source)
        self.meeting_day = defaultdict(list)
        self.clicks = defaultdict(int)  # (day, channel) -> clicks from real people
        self.web_sessions_today = {}
        self.sid = 0

    def identify(self, p, d, source):
        if p not in self.first_identified:
            self.first_identified[p] = (d, source)


# ---------------------------------------------------------------------- simulate
def simulate(W: World, cfg: dict, n_days: int, start: dt.date, disabled=frozenset(), rec: Recorder | None = None, rep: int = 0):
    ch, fn = cfg["channels"], cfg["funnel"]
    P, A = W.P, W.A
    acct, fitp = W.acct_of, W.fit[W.acct_of]
    decay = 0.5 ** (1 / cfg["intent"]["half_life_days"])
    I = np.zeros(P)
    last_web = np.full(P, -10**6)
    stage = np.zeros(P, dtype=np.int8)       # 0 none, 1 lead, 2 in meeting/opp
    lead_day = np.full(P, -1)
    email_day = np.full(P, -1)
    sig_day = np.full(P, -1)
    customer = np.zeros(A, dtype=bool)
    open_until = np.full(A, -1)
    cooldown = np.zeros(A, dtype=int)
    closes = defaultdict(list)
    opps = []
    e_off = np.array(ch["cold_email"]["step_offsets_days"])
    s_off = np.array(ch["signal_engine"]["step_offsets_days"])
    seed = cfg["seed"]

    def on(name):
        return name not in disabled

    for d in range(n_days):
        rng = np.random.default_rng([seed, d] if rep == 0 else [seed, 10**7 + rep, d])
        U = rng.random((NU, P))

        for o in closes.pop(d, []):
            if o["won"]:
                customer[o["acct"]] = True
            else:
                cooldown[o["acct"]] = d + fn["lost_cooldown_days"]
                stage[o["person"]] = 0

        active = ~customer[acct]
        I *= decay
        I[(U[0] < cfg["intent"]["dark_funnel_daily_p"]) & active] += cfg["intent"]["dark_funnel_lift"]
        sat = 1 - np.exp(-I / 2)
        zero = np.zeros(P, dtype=bool)

        def expo(name, prob, k):
            return (U[k] < prob) & active if on(name) else zero

        c = ch
        li = expo("linkedin_ads", c["linkedin_ads"]["p_base"] * fitp, 1)
        go = expo("google_ads", c["google_ads"]["p_base"] + c["google_ads"]["p_intent"] * sat, 2)
        rt = expo("retargeting_ads", np.where(d - last_web <= 30, c["retargeting_ads"]["p_recent_visitor"], 0.0), 3)
        org = expo("organic_search", c["organic_search"]["p_base"] + c["organic_search"]["p_intent"] * sat, 4)
        dr = expo("direct", c["direct"]["p_base"] + c["direct"]["p_intent"] * sat, 5)
        ref = expo("referral", c["referral"]["p_base"], 6)
        web = {"linkedin_ads": li, "google_ads": go, "retargeting_ads": rt,
               "organic_search": org, "direct": dr, "referral": ref}

        ce = c["cold_email"]
        if on("cold_email"):
            enroll = (email_day < 0) & (stage == 0) & (U[7] < ce["p_enroll"] * fitp) & active
            email_day[enroll] = d
            estep = (email_day >= 0) & np.isin(d - email_day, e_off) & active
        else:
            enroll = estep = zero
        eclick = estep & (U[8] < ce["p_click"])
        ereply = estep & (U[9] < ce["p_reply"])
        epos = ereply & (U[10] < ce["p_positive"])

        se = c["signal_engine"]
        if on("signal_engine"):
            sdet = (sig_day < 0) & (U[11] < se["p_base"] + se["p_intent"] * sat) & active
            sig_day[sdet] = d
            sstep = (sig_day >= 0) & np.isin(d - sig_day, s_off) & active
        else:
            sdet = sstep = zero
        sreply = sstep & (U[12] < se["p_reply"])
        spos = sreply & (U[13] < se["p_positive"])
        pos = epos | spos
        rbot = pos & (U[14] < c["reply_bot"]["p_handles_positive_reply"]) if on("reply_bot") else zero

        lift = np.zeros(P)
        for name, m in web.items():
            lift += m * c[name]["true_lift"]
        lift += eclick * ce["true_lift_click"] + ereply * ce["true_lift_reply_negative"]
        lift += epos * (ce["true_lift_reply_positive"] - ce["true_lift_reply_negative"])
        lift += sdet * se["true_lift_detect"] + spos * se["true_lift_reply_positive"]
        lift += rbot * c["reply_bot"]["true_lift"]
        I += lift
        # retargeting audiences are built from organic/paid visits, not from retargeting clicks
        last_web[li | go | org | dr | ref] = d

        sat = 1 - np.exp(-I / 2)
        form = (stage == 0) & ~pos & (U[15] < fn["form_fill_p_base"] + fn["form_fill_p_intent"] * sat) & active
        new_lead = (stage == 0) & (pos | form) & active
        stage[new_lead] = 1
        lead_day[new_lead] = d
        va = new_lead & (U[16] < c["voice_agent"]["p_calls_new_lead"]) if on("voice_agent") else zero
        I[va] += c["voice_agent"]["true_lift"]
        stage[(stage == 1) & (d - lead_day > fn["lead_stale_after_days"])] = 0

        sat2 = 1 - np.exp(-I / 2.5)
        meet = (stage == 1) & (d > lead_day) & (U[17] < fn["meeting_p_base"] + fn["meeting_p_intent"] * sat2) & active
        # meetings that start offline (events, intros to the founders): no digital touch at all
        meet |= (stage == 0) & (U[32] < fn["offline_meeting_p"] * fitp) & active
        meet_idx = np.nonzero(meet)[0]
        if len(meet_idx):
            acct_I = np.bincount(acct, weights=I, minlength=A)
        for p in meet_idx:
            a = acct[p]
            stage[p] = 2
            if rec is not None:
                rec.meeting_day[p].append(d)
            if open_until[a] >= d or d < cooldown[a]:
                stage[p] = 0
                continue
            if U[18][p] >= min(fn["qualify_p_max"], fn["qualify_p_base"] + fn["qualify_p_fit"] * W.fit[a]):
                stage[p] = 0
                continue
            band = size_band(W.employees[a])
            z = math.sqrt(-2 * math.log(max(U[19][p], 1e-12))) * math.cos(2 * math.pi * U[20][p])
            amount = round(fn["deal_amount_median_by_size"][band] * math.exp(fn["deal_amount_sigma"] * z), -2)
            cycle = int(fn["cycle_days_min"] + fn["cycle_days_spread"] * U[21][p] * (amount / 22000) ** 0.3)
            p_win = min(fn["win_p_max"], (fn["win_p_base"] + fn["win_p_intent"] * (1 - math.exp(-(I[p] + 0.3 * (acct_I[a] - I[p])) / 3))) * W.fit[a] / 0.8)
            won = bool(U[22][p] < p_win)
            o = {"idx": len(opps), "acct": a, "person": p, "created": d, "close": d + cycle,
                 "amount": amount, "won": won, "u_mess": float(U[23][p]), "u_mess2": float(U[24][p])}
            opps.append(o)
            closes[d + cycle].append(o)
            open_until[a] = d + cycle

        if rec is not None:
            _record_day(W, cfg, rec, d, start, U, rng, web, enroll, estep, eclick, ereply, epos,
                        sdet, sstep, sreply, spos, rbot, form, new_lead, va)

    won_rev = sum(o["amount"] for o in opps if o["won"] and o["close"] < n_days)
    return opps, won_rev


# ---------------------------------------------------------------------- recording
def ts(start, d, frac):
    t = dt.datetime.combine(start + dt.timedelta(days=d), dt.time()) + dt.timedelta(seconds=int(frac * 86399))
    return t


def iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def _record_day(W, cfg, rec, d, start, U, rng, web, enroll, estep, eclick, ereply, epos,
                sdet, sstep, sreply, spos, rbot, form, new_lead, va):
    ch, pm = cfg["channels"], cfg["paid_media"]
    day = start + dt.timedelta(days=d)
    li_rename = dt.date.fromisoformat(pm["linkedin_utm_rename_date"])
    sig_rename = dt.date.fromisoformat(pm["signal_campaign_rename_date"])
    today_session = {}

    def session(p, channel, frac):
        rec.sid += 1
        dev = 1 if (W.two_devices[p] and U[25][p] < 0.4) else 0
        cid = W.client_ids[p][dev]
        src = med = camp = ref = None
        missing = U[26][p] < ch.get(channel, {}).get("utm_missing", 0)
        if channel == "linkedin_ads":
            if missing:
                ref = "linkedin.com" if U[27][p] < 0.5 else None
            else:
                src, med = ("linkedin" if day < li_rename else "linkedin_ads"), ("paid_social" if day < li_rename else "cpc")
                camp = "li_icp_legal_ops"
        elif channel == "google_ads":
            if not missing:
                src, med, camp = "google", "cpc", "brand_and_category"
            else:
                ref = "google.com"
        elif channel == "retargeting_ads":
            if not missing:
                src, med, camp = "adroll", "display", "rt_site_visitors_30d"
        elif channel == "organic_search":
            ref = "google.com"
        elif channel == "referral":
            ref = ["g2.com", "legaltechpartners.io", "capterra.com"][int(U[27][p] * 3)]
        page = ["/", "/pricing", "/product/contract-review", "/blog/redline-faster", "/case-studies"][int(U[28][p] * 5)]
        row = {"session_id": f"s{rec.sid:08d}", "client_id": cid, "session_start": iso(ts(start, d, frac)),
               "utm_source": src, "utm_medium": med, "utm_campaign": camp, "referrer": ref, "landing_page": page}
        rec.rows["ga4_sessions"].append(row)
        return row

    for name, m in web.items():
        for p in np.nonzero(m)[0]:
            today_session[p] = session(p, name, U[29][p] * 0.9)
            if name in pm["cpc_usd"]:
                rec.clicks[(d, name)] += 1

    # anonymous junk traffic that never becomes a known person
    for name, lam in pm["junk_clicks_per_day"].items():
        n = rng.poisson(lam)
        rec.clicks[(d, name)] += n
        for _ in range(n):
            rec.sid += 1
            rec.rows["ga4_sessions"].append({
                "session_id": f"s{rec.sid:08d}", "client_id": f"{rng.integers(10**9, 2*10**9)}.{rng.integers(1_600_000_000, 1_700_000_000)}",
                "session_start": iso(ts(start, d, rng.random())),
                "utm_source": {"linkedin_ads": "linkedin" if day < li_rename else "linkedin_ads", "google_ads": "google", "retargeting_ads": "adroll"}[name],
                "utm_medium": {"linkedin_ads": "paid_social" if day < li_rename else "cpc", "google_ads": "cpc", "retargeting_ads": "display"}[name],
                "utm_campaign": None, "referrer": None, "landing_page": "/"})
            if rng.random() < cfg["channels"][name]["utm_missing"]:
                row = rec.rows["ga4_sessions"][-1]
                row["utm_source"] = row["utm_medium"] = None

    # cold email
    for p in np.nonzero(enroll)[0]:
        rec.identify(p, d, "cold_email")
    for p in np.nonzero(estep)[0]:
        t = ts(start, d, 0.35 + 0.1 * U[30][p])
        camp = f"outbound_{W.industry[W.acct_of[p]].lower().replace(' ', '_').replace('-', '')}_seq"
        base = {"campaign_name": camp, "lead_email": W.email[p]}
        rec.rows["smartlead_email_events"].append({**base, "event_type": "sent", "event_time": iso(t), "reply_category": None})
        if U[31][p] < ch["cold_email"]["p_open"]:
            rec.rows["smartlead_email_events"].append({**base, "event_type": "open", "event_time": iso(t + dt.timedelta(hours=2)), "reply_category": None})
        if eclick[p]:
            rec.rows["smartlead_email_events"].append({**base, "event_type": "click", "event_time": iso(t + dt.timedelta(hours=3)), "reply_category": None})
        if ereply[p]:
            cat = "interested" if epos[p] else ("not_interested" if U[27][p] < 0.7 else "out_of_office")
            rec.rows["smartlead_email_events"].append({**base, "event_type": "reply", "event_time": iso(t + dt.timedelta(hours=5)), "reply_category": cat})

    # signal engine
    for p in np.nonzero(sdet)[0]:
        rec.identify(p, d, "signal_engine")
        miss = U[26][p] < ch["signal_engine"]["email_missing"]
        rec.rows["clay_signal_leads"].append({
            "linkedin_post_url": POSTS[int(U[27][p] * len(POSTS))],
            "commenter_name": f"{W.first[p]} {W.last[p]}", "commenter_title": W.title[p],
            "company_domain": W.acct_domain[W.acct_of[p]], "work_email": None if miss else W.email[p],
            "detected_at": iso(ts(start, d, U[28][p]))})
    for p in np.nonzero(sstep)[0]:
        t = ts(start, d, 0.4 + 0.1 * U[30][p])
        camp = "clay_signal_commenters" if day < sig_rename else "sig_post_commenters"
        base = {"campaign_name": camp, "lead_email": W.email[p]}
        rec.rows["smartlead_email_events"].append({**base, "event_type": "sent", "event_time": iso(t), "reply_category": None})
        if sreply[p]:
            cat = "interested" if spos[p] else "not_interested"
            rec.rows["smartlead_email_events"].append({**base, "event_type": "reply", "event_time": iso(t + dt.timedelta(hours=4)), "reply_category": cat})

    # reply bot reads every reply; it only acts on positive ones
    for p in np.nonzero(ereply | sreply)[0]:
        t = ts(start, d, 0.4 + 0.1 * U[30][p]) + dt.timedelta(hours=5)
        positive = bool(epos[p] or spos[p])
        rec.rows["reply_bot_threads"].append({
            "lead_email": W.email[p], "inbound_at": iso(t),
            "intent_label": "interested" if positive else "not_interested",
            "bot_replied_at": iso(t + dt.timedelta(minutes=2 + int(U[29][p] * 7))) if rbot[p] else None,
            "handed_off_to_human": "true" if not rbot[p] else "false"})

    # form fills
    for p in np.nonzero(form)[0]:
        frac = 0.92 + 0.07 * U[30][p]
        s = today_session.get(p) or session(p, "direct_conversion", frac)
        personal = W.dup[p] and U[27][p] < 0.7
        email = f"{W.first[p].lower()}{W.last[p].lower()}{p % 97}@gmail.com" if personal else W.email[p]
        rec.rows["ga4_form_fills"].append({"session_id": s["session_id"], "client_id": s["client_id"],
                                           "email": email, "form_name": "demo_request", "submitted_at": iso(ts(start, d, frac))})
        rec.identify(p, d, "form")
        if personal:
            rec.rows["_personal_dups"].append({"p": p, "email": email, "day": d})

    for p in np.nonzero(new_lead)[0]:
        rec.identify(p, d, "lead")
        rec.rows["_leads"].append({"p": p, "day": d})
    for p in np.nonzero(va)[0]:
        t = ts(start, d, 0.95) + dt.timedelta(hours=5, minutes=30 + 1 + int(U[29][p] * 3))  # IST, no tz
        rec.rows["_voice"].append({"p": p, "day": d, "t": t})


# ------------------------------------------------------------------- finalize
def finalize(W, cfg, rec, opps, start, n_days, out_dir):
    fn, mess = cfg["funnel"], cfg["data_mess"]
    end = start + dt.timedelta(days=n_days)
    rng = np.random.default_rng([cfg["seed"], 424242])
    for p in {o["person"] for o in opps}:
        rec.identify(p, next(o["created"] for o in opps if o["person"] == p), "meeting")

    # HubSpot companies
    comp_id = {a: 7_100_000_000 + a * 13 for a in range(W.A)}
    rec.rows["hubspot_companies"] = [{
        "hs_object_id": comp_id[a], "name": W.acct_name[a], "domain": W.acct_domain[a],
        "industry": W.industry[a].upper().replace(" ", "_").replace("-", "_"),
        "numberofemployees": int(W.employees[a]),
        "createdate": iso(ts(start, -int(rng.integers(5, 200)), rng.random()))} for a in range(W.A)]

    # HubSpot contacts
    won_accts = {o["acct"]: o for o in opps if o["won"] and o["close"] < n_days}
    leads = {r["p"] for r in rec.rows["_leads"]}
    contact_id = {}
    contacts = []
    for i, (p, (d, src)) in enumerate(sorted(rec.first_identified.items())):
        cid = 90_000_000 + i * 7
        contact_id[p] = cid
        a = W.acct_of[p]
        life = "customer" if a in won_accts else ("opportunity" if any(o["person"] == p for o in opps) else ("lead" if p in leads else "subscriber"))
        ph = W.phone_digits[p]
        contacts.append({"hs_object_id": cid, "email": W.email[p], "firstname": W.first[p], "lastname": W.last[p],
                         "jobtitle": W.title[p], "phone": f"+1 ({ph[:3]}) {ph[3:6]}-{ph[6:]}",
                         "associatedcompanyid": comp_id[a], "lifecyclestage": life,
                         "createdate": iso(ts(start, d, 0.5))})
    seen_dup = set()
    for r in rec.rows["_personal_dups"]:
        if r["email"] in seen_dup:
            continue
        seen_dup.add(r["email"])
        p = r["p"]
        contacts.append({"hs_object_id": 95_000_000 + len(seen_dup), "email": r["email"], "firstname": W.first[p],
                         "lastname": W.last[p], "jobtitle": None, "phone": W.phone_digits[p],
                         "associatedcompanyid": None, "lifecyclestage": "lead", "createdate": iso(ts(start, r["day"], 0.93))})
    rec.rows["hubspot_contacts"] = contacts

    # HubSpot deals + stage history (with deliberate mess)
    deals, hist = [], []
    for o in opps:
        deal_id = 30_000_000_000 + o["idx"] * 31
        created = ts(start, o["created"], 0.6)
        closed = o["close"] < n_days
        a = W.acct_of[o["person"]]
        stages = list(DEAL_STAGES)
        if o["u_mess"] < mess["deal_stage_skip_share"]:
            stages.pop(1 + int(o["u_mess2"] * 3))
        span = o["close"] - o["created"]
        entries = [(s, created + dt.timedelta(days=int(span * k / len(stages)))) for k, s in enumerate(stages)]
        entries = [(s, t) for s, t in entries if t.date() < end]
        reopened = o["won"] and closed and span > 40 and \
            np.random.default_rng([cfg["seed"], 555, o["idx"]]).random() < mess["lost_then_reopened_share"]
        if closed:
            close_t = ts(start, o["close"], 0.7)
            if reopened:
                entries.append(("closedlost", close_t - dt.timedelta(days=30)))
                entries.append(("contractsent", close_t - dt.timedelta(days=10)))
            entries.append(("closedwon" if o["won"] else "closedlost", close_t))
        entries.sort(key=lambda x: x[1])
        for s, t in entries:
            hist.append({"deal_id": deal_id, "dealstage": s, "changed_at": iso(t)})
        current = entries[-1][0]
        deals.append({"hs_object_id": deal_id, "dealname": f"{W.acct_name[a]} - Quillstack",
                      "amount": f"{o['amount']:.2f}", "pipeline": "default", "dealstage": current,
                      "createdate": iso(created),
                      "closedate": iso(ts(start, o["close"], 0.7)) if closed else iso(ts(start, o["close"], 0.7)),
                      "hs_is_closed": "true" if closed else "false",
                      "associatedcompanyid": comp_id[a],
                      "associatedcontactid": None if o["u_mess"] > 1 - mess["deal_missing_contact_share"] else contact_id.get(o["person"])})
    rec.rows["hubspot_deals"] = deals
    rec.rows["hubspot_deal_stage_history"] = hist

    # voice agent calls (IST local time, no timezone)
    for r in rec.rows["_voice"]:
        p = r["p"]
        booked = any(0 < md - r["day"] <= 2 for md in rec.meeting_day.get(p, []))
        outcome = "meeting_booked" if booked else ["no_answer", "not_qualified", "call_back_later"][int(rng.random() * 3)]
        ph = W.phone_digits[p]
        rec.rows["voice_agent_calls"].append({"call_id": f"call_{len(rec.rows['voice_agent_calls']) + 1:06d}",
                                              "lead_email": W.email[p], "phone": f"+1{ph}",
                                              "called_at_ist": r["t"].strftime("%Y-%m-%d %H:%M:%S"),
                                              "duration_sec": int(20 + rng.random() * 400), "outcome": outcome})

    # ad platforms daily
    li, go, rt = [], [], []
    cpc = cfg["paid_media"]["cpc_usd"]
    for d in range(n_days):
        date = (start + dt.timedelta(days=d)).isoformat()
        c1, c2, c3 = rec.clicks[(d, "linkedin_ads")], rec.clicks[(d, "google_ads")], rec.clicks[(d, "retargeting_ads")]
        li.append({"date": date, "campaign_name": "li_icp_legal_ops", "impressions": int(c1 * rng.uniform(90, 160)),
                   "clicks": c1, "cost_in_usd": f"{c1 * cpc['linkedin_ads'] * rng.uniform(0.85, 1.15):.2f}"})
        go.append({"segments_date": date, "campaign_name": "brand_and_category", "metrics_clicks": c2,
                   "metrics_cost_micros": int(c2 * cpc["google_ads"] * rng.uniform(0.85, 1.15) * 1_000_000)})
        rt.append({"day": date, "campaign": "rt_site_visitors_30d", "clicks": c3,
                   "spend": f"{c3 * cpc['retargeting_ads'] * rng.uniform(0.85, 1.15):.2f}"})
    rec.rows["linkedin_ads_daily"], rec.rows["google_ads_daily"], rec.rows["adroll_daily"] = li, go, rt

    # Stripe subscriptions + monthly movements
    rt_cfg = cfg["retention"]
    subs, events = [], []
    for o in opps:
        if not (o["won"] and o["close"] < n_days):
            continue
        srng = np.random.default_rng([cfg["seed"], 777, o["idx"]])
        a = W.acct_of[o["person"]]
        sub_id = f"sub_{o['idx']:05d}"
        mrr = int(round(o["amount"] / 12 * 100))
        start_d = start + dt.timedelta(days=o["close"])
        status = "active"
        events.append({"subscription_id": sub_id, "event_type": "new", "mrr_delta_cents": mrr, "occurred_on": start_d.isoformat()})
        m = 1
        while True:
            month = start_d + dt.timedelta(days=30 * m)
            if month >= end:
                break
            u = srng.random()
            if u < rt_cfg["monthly_churn_p"]:
                events.append({"subscription_id": sub_id, "event_type": "churn", "mrr_delta_cents": -mrr, "occurred_on": month.isoformat()})
                status, mrr = "canceled", 0
                break
            elif u < rt_cfg["monthly_churn_p"] + rt_cfg["monthly_expansion_p"]:
                delta = int(mrr * srng.uniform(0.1, 0.4))
                events.append({"subscription_id": sub_id, "event_type": "expansion", "mrr_delta_cents": delta, "occurred_on": month.isoformat()})
                mrr += delta
            elif u < rt_cfg["monthly_churn_p"] + rt_cfg["monthly_expansion_p"] + rt_cfg["monthly_contraction_p"]:
                delta = -int(mrr * srng.uniform(0.1, 0.3))
                events.append({"subscription_id": sub_id, "event_type": "contraction", "mrr_delta_cents": delta, "occurred_on": month.isoformat()})
                mrr += delta
            m += 1
        subs.append({"id": sub_id, "customer_domain": W.acct_domain[a], "status": status,
                     "start_date": start_d.isoformat(), "current_mrr_cents": mrr})
    rec.rows["stripe_subscriptions"], rec.rows["stripe_subscription_events"] = subs, events

    os.makedirs(out_dir, exist_ok=True)
    for name, rows in rec.rows.items():
        if name.startswith("_") or not rows:
            continue
        write_csv(os.path.join(out_dir, f"{name}.csv"), rows)
    return {k: len(v) for k, v in rec.rows.items() if not k.startswith("_")}


def write_csv(path, rows):
    cols = list(rows[0].keys())
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in cols})


# ----------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(ROOT, "config", "world.yml"))
    ap.add_argument("--end-date", default=None, help="YYYY-MM-DD (overrides config)")
    ap.add_argument("--out", default=os.path.join(ROOT, "data"))
    ap.add_argument("--skip-truth", action="store_true", help="skip the counterfactual ground-truth runs")
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.config))
    start = dt.date.fromisoformat(cfg["history_start"])
    end_s = args.end_date or cfg["end_date"]
    end = dt.date.today() if end_s == "today" else dt.date.fromisoformat(str(end_s))
    n_days = (end - start).days
    W = World(cfg)
    print(f"World: {cfg['company']['name']} | {W.A} accounts, {W.P} people | {start} -> {end} ({n_days} days)")

    rec = Recorder()
    opps, won_rev = simulate(W, cfg, n_days, start, rec=rec)
    counts = finalize(W, cfg, rec, opps, start, n_days, os.path.join(args.out, "raw"))
    for k, v in sorted(counts.items()):
        print(f"  {k:32s} {v:>8,}")
    n_won = sum(1 for o in opps if o["won"] and o["close"] < n_days)
    print(f"  opportunities {len(opps)}, closed-won {n_won}, won revenue ${won_rev:,.0f}")

    if not args.skip_truth:
        # Expected incremental revenue per channel: average over replicate worlds (same companies
        # and people, different daily luck), each run with and without the channel.
        K = int(cfg.get("truth_replicates", 8))
        base = [won_rev] + [simulate(W, cfg, n_days, start, rep=r)[1] for r in range(1, K)]
        truth = []
        for c in CHANNELS:
            inc = np.array([base[r] - simulate(W, cfg, n_days, start, disabled=frozenset([c]), rep=r)[1] for r in range(K)])
            truth.append({"channel": c, "replicates": K,
                          "expected_incremental_revenue": f"{inc.mean():.2f}",
                          "std_error": f"{inc.std(ddof=1) / math.sqrt(K):.2f}",
                          "expected_won_revenue": f"{np.mean(base):.2f}"})
            print(f"  truth: {c:16s} expected incremental ${inc.mean():>10,.0f}  (+/- {inc.std(ddof=1) / math.sqrt(K):,.0f})")
        os.makedirs(os.path.join(args.out, "truth"), exist_ok=True)
        write_csv(os.path.join(args.out, "truth", "channel_incrementality.csv"), truth)


if __name__ == "__main__":
    main()
