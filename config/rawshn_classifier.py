"""PM-oriented job filter overrides for Rawshn (USE_RAWSHN_CONFIG=1)."""

import json
import re

import requests

from src.client.jop_classifier import JobFilterPipeline2


class JobFilterPipelinePM(JobFilterPipeline2):
    MY_STACK = [
        "product management", "product manager", "product strategy", "product roadmap",
        "prd", "user research", "gtm", "stakeholder", "prioritization",
        "b2b saas", "hr tech", "hrtech", "edtech", "marketplace", "enterprise",
        "onboarding", "implementation", "integration", "ats", "talent",
        "ai", "ml", "llm", "generative ai", "genai", "prompt engineering",
        "figma", "sql", "jira", "analytics", "mixpanel", "amplitude",
        "a/b testing", "ux", "ui", "agile", "scrum", "api",
    ]

    VETO_TITLES = [
        "walk-in", "walkin", "walk in",
        "android developer", "ios developer", "flutter developer",
        "frontend developer", "front-end developer",
        "principal engineer", "staff engineer",
        "vp of engineering", "head of engineering", "head of technology",
        "founder", "tutor", "trainer",
        "data scientist", "ml engineer", "data engineer", "intern", "internship",
        "engineering manager", "etl engineer", "prompt engineer",
        "sales manager", "account manager", "project manager",
        "marketing manager", "brand marketing manager", "digital marketing manager",
        "analyst", "associate is engineer", "infra engineer",
        "observability engineer",
    ]

    SOFTWARE_KEYWORDS = {
        "product", "manager", "pm", "owner", "program",
        "software", "engineer", "developer", "technology",
        "saas", "platform", "growth", "strategy",
    }

    FRONTEND_VETO_KEYWORDS = {
        "android", "ios", "flutter", "mobile", "kotlin", "swift",
        "embedded", "firmware", "intern", "internship",
    }

    def experience_filter(self, jobs):
        # Keep roles overlapping 3-7 years (search EXPERIENCE_LEVELS + classifier alignment).
        return [
            j for j in jobs
            if j.get("experience_min", 0) <= 7
            and j.get("experience_max", 10) >= 3
        ]

    def _call_ai(self, jobs):
        job_block = ""
        for i, j in enumerate(jobs):
            mandatory = ", ".join(j.get("mandatory_tags", [])) or "none"
            optional = ", ".join(j.get("optional_tags", [])) or "none"
            exp = f"{j.get('experience_min', 0)}-{j.get('experience_max', 10)} yrs"
            job_block += (
                f"Job {i}:\n"
                f"  Title:     {j.get('title')}\n"
                f"  Company:   {j.get('company')}\n"
                f"  Mandatory: {mandatory}\n"
                f"  Optional:  {optional}\n"
                f"  Exp:       {exp}\n"
                f"  Days old:  {j.get('days_old', 7)}\n"
                f"---\n"
            )

        prompt = f"""
You are a strict job filter for a Product Manager candidate. Score each job 0-100.
Use the full range; avoid clustering every job at 85 or 60.

CANDIDATE:
- 6 years total experience (3+ in product management)
- Core PM: product strategy, PRDs, roadmap, user research, GTM, stakeholder management
- Domain: B2B SaaS, HR tech, EdTech, marketplaces, enterprise onboarding and integrations
- Technical depth: ATS integrations, API scope, AI/ML products, LLM growth tools, SQL, Figma
- Recent: Phenom (enterprise ATS onboarding), Interview Kickstart, Unstop, Herkey
- Foundation: application security at Deloitte and Optum
- Target titles: Product Manager, Senior PM, AI PM, Technical PM, Implementation PM
- Location: Hyderabad (open to Pune, Bengaluru, and remote India), immediate joiner
- Target comp: ~24 LPA INR flexible
- No marketing management experience; skip pure marketing manager roles

SCORING RUBRIC:

90-100: Strong PM fit, apply immediately
  PM or Senior PM title + B2B SaaS/HR tech/marketplace domain + 3-8 yrs exp
  Tags overlap with product strategy, onboarding, integrations, AI, analytics

75-89: Good PM fit, apply
  PM-adjacent title (Product Owner, Growth PM) with relevant domain tags
  Some stack overlap, exp 3-8 yrs

55-74: Decent fit, lower priority
  Generic "Manager" or mixed role but some PM tags present
  Exp borderline (2 yrs min or 8+ yrs max)

30-54: Weak fit, skip unless pipeline is thin
  Project manager, analyst, or tech-heavy with little PM signal

0-29: Do not apply
  Pure engineering (Android, iOS, backend-only SDE), data science, sales, intern
  Walk-in, tutor, trainer, or zero PM/domain overlap

RULES:
- "Product Manager" + HR tech / SaaS tags -> 85+
- "Project Manager" without product tags -> 20-40
- Pure developer/engineer titles -> 0-15
- Implementation PM with onboarding/integration tags -> 80+
- Recency: 0-1 days old -> mentally add 5 points

Return ONLY valid JSON:
{{
  "0": {{"score": 92, "reason": "Senior PM, HR tech, onboarding tags, 5-8 yrs"}},
  "1": {{"score": 5,  "reason": "Android developer, zero PM overlap"}}
}}

Jobs:
{job_block}
"""

        try:
            res = requests.post(
                self.url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                },
                timeout=90,
            )

            if res.status_code != 200:
                print("AI HTTP ERROR:", res.status_code, res.text[:200])
                return {}

            content = res.json()["choices"][0]["message"]["content"]
            content = re.sub(r"```json|```", "", content).strip()
            match = re.search(r"\{.*\}", content, re.S)
            if not match:
                print("AI PARSE ERROR - raw:", content[:300])
                return {}

            data = json.loads(match.group(0))
            return data if isinstance(data, dict) else {}

        except Exception as e:
            print("AI call error:", e)
            return {}
