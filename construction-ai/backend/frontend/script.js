document.addEventListener("DOMContentLoaded", () => {
    const tabs = document.querySelectorAll(".tab-button");
    const tabContents = document.querySelectorAll(".tab-content");
    const chatInput = document.getElementById("chat-input-text");
    const sendChatBtn = document.getElementById("send-chat-btn");
    const chatContainer = document.getElementById("chat-container");
    const imageInput = document.getElementById("image-input");
    const analyzeImageBtn = document.getElementById("analyze-image-btn");
    const researchInput = document.getElementById("research-input");
    const researchBtn = document.getElementById("research-btn");
    const resultsContainer = document.getElementById("results-container");
    const estimatorInput = document.getElementById("estimator-input");
    const estimatorBtn = document.getElementById("estimator-btn");


    let threadId = Date.now().toString();

    tabs.forEach((tab) => {
        tab.addEventListener("click", () => {
            tabs.forEach((t) => t.classList.remove("active"));
            tab.classList.add("active");

            tabContents.forEach((content) => {
                content.classList.remove("active");
                if (content.id === tab.dataset.tab) {
                    content.classList.add("active");
                }
            });
        });
    });

    sendChatBtn.addEventListener("click", async () => {
        const message = chatInput.value;
        if (!message) return;

        appendMessage("user", message);
        chatInput.value = "";

        try {
            const response = await fetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message, thread_id: threadId }),
            });
            const data = await response.json();
            appendMessage("agent", data.response);
        } catch (error) {
            appendMessage("agent", `Error: ${error.message}`);
        }
    });

    analyzeImageBtn.addEventListener("click", async () => {
        const file = imageInput.files[0];
        if (!file) return;

        resultsContainer.innerHTML = "Analyzing...";
        const formData = new FormData();
        formData.append("file", file);

        try {
            const response = await fetch("/api/analyze-image", {
                method: "POST",
                body: formData,
            });
            const data = await response.json();
            displayResults(data.analysis);
        } catch (error) {
            resultsContainer.innerHTML = `Error: ${error.message}`;
        }
    });

    researchBtn.addEventListener("click", async () => {
        const query = researchInput.value;
        if (!query) return;

        resultsContainer.innerHTML = "Searching...";
        try {
            const response = await fetch("/api/research", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ query }),
            });
            const data = await response.json();
            displayResearchResults(data);
        } catch (error) {
            resultsContainer.innerHTML = `Error: ${error.message}`;
        }
    });

    function appendMessage(sender, message) {
        const messageElement = document.createElement("div");
        messageElement.classList.add("chat-message", `${sender}-message`);
        messageElement.innerText = message;
        chatContainer.appendChild(messageElement);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    function displayResults(data) {
        resultsContainer.innerHTML = `
            <h3>Summary</h3>
            <p>${data.summary}</p>
            <h3>Key Findings</h3>
            <ul>
                ${data.key_findings.map((finding) => `<li>${finding}</li>`).join("")}
            </ul>
            <h3>Recommendations</h3>
            <ul>
                ${data.recommendations.map((rec) => `<li>${rec}</li>`).join("")}
            </ul>
            <h3>Next Steps</h3>
            <ul>
                ${data.next_steps.map((step) => `<li>${step}</li>`).join("")}
            </ul>
            <p><em>${data.disclaimer}</em></p>
        `;
    }

    function displayResearchResults(data) {
        resultsContainer.innerHTML = `
            <h3>Summary</h3>
            <p>${data.summary}</p>
            <h3>Results</h3>
            <ul>
                ${data.results.map((result) => `
                    <li>
                        <a href="${result.url}" target="_blank">${result.title}</a>
                        <p>${result.content}</p>
                    </li>
                `).join("")}
            </ul>
        `;
    }

    estimatorBtn.addEventListener("click", async () => {
        const task = estimatorInput.value;
        if (!task) return;

        resultsContainer.innerHTML = "Estimator is running, please wait...";
        try {
            const response = await fetch("/api/run-estimator", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ task }),
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || "Something went wrong");
            }

            const data = await response.json();
            displayEstimatorResult(data);

        } catch (error) {
            resultsContainer.innerHTML = `Error: ${error.message}`;
        }
    });

    function displayEstimatorResult(data) {
        let artifactHtml = "";
        if (data.artifact_path) {
            artifactHtml = `
                <h3>Artifact Created</h3>
                <p>A report file was created: <strong>${data.artifact_path}</strong>. Check your backend project folder.</p>
            `;
        }

        resultsContainer.innerHTML = `
            <h3>Estimator Response</h3>
            <p>${data.response}</p>
            ${artifactHtml}
        `;
    }
});
