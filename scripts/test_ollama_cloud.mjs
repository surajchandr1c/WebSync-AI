/**
 * Test script sending a chat request to Ollama Cloud API (https://ollama.com)
 * using model gemma4:31b and printing the reply.
 * Run with: node --env-file=.env scripts/test_ollama_cloud.mjs
 */

async function main() {
  const apiKey = process.env.OLLAMA_API_KEY;
  if (!apiKey) {
    console.error('Error: OLLAMA_API_KEY environment variable is not set.');
    process.exit(1);
  }

  const response = await fetch('https://ollama.com/api/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      model: 'gemma4:31b',
      messages: [
        { role: 'user', content: 'Why is the sky blue? Explain in two clear sentences.' }
      ],
      stream: false,
    }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    console.error(`Error (${response.status}): ${errorText}`);
    process.exit(1);
  }

  const data = await response.json();
  const reply = data.message?.content || '';
  console.log(reply);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
