/* ===========================
   FUN FACT GENERATOR
=========================== */
function showFunFact() {
    const funFacts = [
        "I can automate workflows faster than I can cook Maggi 🍜",
        "My brain thinks in SQL queries 🧠",
        "I love explaining analytics in the simplest way possible!",
        "I have worked on 30+ analytics & automation projects 🚀",
        "Data cleaning is my therapy 😌",
        "I teach data concepts to students in fun ways!",
        "I can break down any complex topic into simple steps."
    ];

    const randomFact = funFacts[Math.floor(Math.random() * funFacts.length)];

    alert("✨ Fun Fact: " + randomFact);
}

/* ===========================
   SKILLS METER (BASIC DEMO)
=========================== */
function showSkillMeter() {
    alert("📊 Skills Meter:\n\nPython: 90%\nSQL: 85%\nPower BI: 88%\nMachine Learning: 80%\nStorytelling: 95%");
}

/* ===========================
   MINI QUIZ — ANALYST ROLE
=========================== */
function startQuiz() {
    let answer = prompt("What do you enjoy more?\n\nA: Finding patterns in data\nB: Creating dashboards\nC: Solving business problems\nD: Working with models\n\nType A, B, C, or D:");

    if (!answer) return;

    answer = answer.toUpperCase();

    const roles = {
        A: "📈 You are a **Data Analyst**! You love insights, patterns, and exploration.",
        B: "📊 You are a **Business Intelligence Analyst**! Dashboards are your playground.",
        C: "🧠 You are a **Strategy Analyst**! You think big-picture.",
        D: "🤖 You are a **Machine Learning Analyst**! You love models & predictions."
    };

    alert(roles[answer] || "Please enter A, B, C, or D!");
}

