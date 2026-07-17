import { describe, expect, it, vi } from 'vitest'
import { parseSseFrames, streamMessage } from '@/lib/api/conversations'

function streamFromStrings(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder()
  let index = 0
  return new ReadableStream({
    pull(controller) {
      if (index < chunks.length) {
        controller.enqueue(encoder.encode(chunks[index]))
        index += 1
      } else {
        controller.close()
      }
    },
  })
}

describe('parseSseFrames', () => {
  it('splits complete frames and keeps the partial remainder', () => {
    const { frames, rest } = parseSseFrames(
      'event: delta\ndata: {"text":"Hi"}\n\nevent: delta\ndata: {"text":"!"}\n\nevent: do'
    )
    expect(frames).toHaveLength(2)
    expect(frames[0]).toEqual({ event: 'delta', data: '{"text":"Hi"}' })
    expect(frames[1]).toEqual({ event: 'delta', data: '{"text":"!"}' })
    expect(rest).toBe('event: do')
  })
})

describe('streamMessage', () => {
  it('renders incremental text, then the final persisted response', async () => {
    const doneResponse = {
      user_message: { id: 'u1', role: 'user', content: 'hi' },
      assistant_message: { id: 'a1', role: 'assistant', content: 'Hi there' },
      conversation: { id: 'c1' },
      products: [],
    }
    const frames = [
      'event: delta\ndata: {"text":"Hi "}\n\n',
      'event: delta\ndata: {"text":"there"}\n\n',
      `event: done\ndata: ${JSON.stringify(doneResponse)}\n\n`,
    ]
    global.fetch = vi
      .fn()
      .mockResolvedValue({
        ok: true,
        status: 200,
        body: streamFromStrings(frames),
      }) as unknown as typeof fetch

    const deltas: string[] = []
    let finalContent = ''
    await streamMessage(
      'c1',
      { content: 'hi' },
      {
        onDelta: (text) => deltas.push(text),
        onDone: (response) => {
          finalContent = response.assistant_message?.content ?? ''
        },
      }
    )

    expect(deltas).toEqual(['Hi ', 'there'])
    expect(finalContent).toBe('Hi there')
  })

  it('throws on a non-OK response so the caller can fall back to blocking', async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue({ ok: false, status: 500, body: null }) as unknown as typeof fetch

    await expect(
      streamMessage('c1', { content: 'hi' }, { onDelta: () => {}, onDone: () => {} })
    ).rejects.toThrow()
  })
})
