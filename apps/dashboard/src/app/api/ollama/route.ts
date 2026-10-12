import { NextRequest, NextResponse } from 'next/server';

/**
 * Server-only API route handler for Ollama Cloud API.
 * Never exposes OLLAMA_API_KEY to the browser client.
 */
export async function POST(req: NextRequest) {
  try {
    const apiKey = process.env.OLLAMA_API_KEY;
    if (!apiKey) {
      return NextResponse.json(
        { error: 'OLLAMA_API_KEY is not configured on the server' },
        { status: 500 }
      );
    }

    const body = await req.json().catch(() => ({}));
    const model = body.model || 'gemma4:31b';
    const prompt = body.prompt || body.message || 'Why is the sky blue?';
    const messages = body.messages || [
      { role: 'user', content: prompt }
    ];

    const ollamaResponse = await fetch('https://ollama.com/api/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model,
        messages,
        stream: false,
      }),
    });

    if (!ollamaResponse.ok) {
      const errText = await ollamaResponse.text();
      return NextResponse.json(
        {
          error: `Ollama Cloud API returned status ${ollamaResponse.status}`,
          details: errText,
        },
        { status: ollamaResponse.status }
      );
    }

    const data = await ollamaResponse.json();
    return NextResponse.json({
      model: data.model || model,
      reply: data.message?.content || '',
      done: data.done,
      total_duration: data.total_duration,
    });
  } catch (error: any) {
    return NextResponse.json(
      { error: error?.message || 'Internal server error calling Ollama Cloud API' },
      { status: 500 }
    );
  }
}
