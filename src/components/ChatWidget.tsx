import { MessageCircle, Send, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { supabase } from "@/integrations/supabase/client";
import { type ChatMessage, sendChat } from "@/lib/flight-api";

const STORAGE_KEY = "flight-chat-history";
const GREETING: ChatMessage = {
  role: "assistant",
  content:
    "嗨！我是 24 小時 AI 機票客服，可以幫你查目前票價、說明方案與收費，登入後還能查你的訂閱。",
};

function loadHistory(): ChatMessage[] {
  try {
    const saved = sessionStorage.getItem(STORAGE_KEY);
    return saved ? (JSON.parse(saved) as ChatMessage[]) : [GREETING];
  } catch {
    return [GREETING];
  }
}

export function ChatWidget() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>(loadHistory);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(messages.slice(-30)));
    } catch {
      // storage can be unavailable (private mode); the chat still works for this page view
    }
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, open]);

  async function send() {
    const text = draft.trim();
    if (!text || busy) return;
    const next = [...messages, { role: "user" as const, content: text }];
    setMessages(next);
    setDraft("");
    setBusy(true);
    try {
      const { data } = await supabase.auth.getSession();
      // The greeting is UI only; the server wants the conversation to start with the user.
      const reply = await sendChat(
        next.filter((m) => m.content !== GREETING.content),
        data.session?.access_token,
      );
      setMessages([...next, { role: "assistant", content: reply }]);
    } catch (err) {
      setMessages([
        ...next,
        {
          role: "assistant",
          content: err instanceof Error ? err.message : "客服暫時無法回應，請稍後再試。",
        },
      ]);
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <Button
        className="fixed bottom-5 right-5 z-50 h-14 w-14 rounded-full shadow-lg"
        aria-label="開啟 AI 客服"
        onClick={() => setOpen(true)}
      >
        <MessageCircle className="h-6 w-6" />
      </Button>
    );
  }

  return (
    <div className="fixed bottom-5 right-5 z-50 flex h-[32rem] max-h-[80vh] w-[22rem] max-w-[calc(100vw-2.5rem)] flex-col overflow-hidden rounded-xl border bg-background shadow-2xl">
      <div className="flex items-center justify-between border-b px-4 py-3">
        <span className="font-semibold">AI 機票客服</span>
        <Button variant="ghost" size="icon" aria-label="關閉客服" onClick={() => setOpen(false)}>
          <X className="h-4 w-4" />
        </Button>
      </div>
      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-3 text-sm">
        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "flex justify-end" : "flex justify-start"}>
            <div
              className={
                "max-w-[85%] whitespace-pre-wrap rounded-lg px-3 py-2 " +
                (m.role === "user" ? "bg-primary text-primary-foreground" : "bg-muted")
              }
            >
              {m.content}
            </div>
          </div>
        ))}
        {busy && <div className="text-muted-foreground">客服輸入中…</div>}
        <div ref={bottomRef} />
      </div>
      <form
        className="flex items-end gap-2 border-t p-3"
        onSubmit={(e) => {
          e.preventDefault();
          void send();
        }}
      >
        <Textarea
          value={draft}
          maxLength={500}
          rows={2}
          placeholder="輸入問題，例如：東京現在多少錢？"
          className="min-h-0 resize-none"
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              void send();
            }
          }}
        />
        <Button type="submit" size="icon" aria-label="送出" disabled={busy || !draft.trim()}>
          <Send className="h-4 w-4" />
        </Button>
      </form>
    </div>
  );
}
