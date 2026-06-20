from agents.developer.developer import developer_agent
from agents.manager.manager import manager_agent
from agents.reviewer.reviewer import reviewer_agent


AGENT_PROFILES = {
    "manager": {
        "name": "Manager Agent",
        "description": "Plans work, delegates tasks, tracks progress, and prepares CEO reports.",
        "capabilities": [
            "Market research",
            "Feature planning",
            "Sprint planning",
            "Progress review"
        ],
        "handler": manager_agent
    },
    "frontend": {
        "name": "Frontend Agent",
        "description": "Plans and implements Vue, Vuetify, PrimeVue, TypeScript, and UX work.",
        "capabilities": ["VueJS", "Vuetify", "PrimeVue", "JavaScript", "TypeScript", "UX"],
        "handler": developer_agent
    },
    "backend": {
        "name": "Backend Agent",
        "description": "Plans and implements Python, .NET, ASP.NET Core, REST, EF, and auth work.",
        "capabilities": ["Python", ".NET 8", "ASP.NET Core", "Entity Framework", "REST APIs"],
        "handler": developer_agent
    },
    "database": {
        "name": "Database Agent",
        "description": "Designs schemas, reviews query performance, and plans migrations.",
        "capabilities": ["SQL Server", "PostgreSQL", "Query optimization", "Schema design"],
        "handler": developer_agent
    },
    "security": {
        "name": "Security Agent",
        "description": "Reviews security risks, dependencies, secrets, privacy, and attack surface.",
        "capabilities": ["Code scanning", "Dependency audits", "Secrets detection", "Privacy reviews"],
        "handler": reviewer_agent
    },
    "testing": {
        "name": "Testing Agent",
        "description": "Plans and reviews unit, integration, UI, regression, and performance tests.",
        "capabilities": ["Unit tests", "Integration tests", "UI tests", "Regression tests"],
        "handler": reviewer_agent
    },
    "marketing": {
        "name": "Marketing Agent",
        "description": "Researches markets and drafts campaigns, ads, landing pages, and posts.",
        "capabilities": ["Competitor analysis", "Keyword research", "Blog posts", "Ads"],
        "handler": manager_agent
    },
    "support": {
        "name": "Support Agent",
        "description": "Classifies tickets, drafts responses, and escalates unresolved issues.",
        "capabilities": ["Ticket triage", "Knowledge base search", "Auto replies", "Dev ticket creation"],
        "handler": manager_agent
    },
}


def get_agent(agent_key):
    return AGENT_PROFILES.get(agent_key, AGENT_PROFILES["manager"])
