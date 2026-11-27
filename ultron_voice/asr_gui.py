"""Native local lab UI for WAV recognition. No automatic capture or service."""
from __future__ import annotations
import queue
import threading
from .asr_supervisor import run_wav, SessionError


class SessionController:
    def __init__(self):
        self.events = queue.Queue(maxsize=2050)
        self.cancel_event = None
        self.thread = None

    @property
    def active(self):
        return self.thread is not None and self.thread.is_alive()

    def start(self, path, language="pt"):
        if self.active or not self.events.empty():
            raise SessionError("ASR_SESSION_BUSY")
        self.cancel_event = threading.Event()
        def work():
            try:
                result = run_wav(path, language=language, cancel=self.cancel_event,
                                 on_event=lambda event: self.events.put_nowait(event))
                self.events.put_nowait(result)
            except Exception as exc:
                code = str(exc) if isinstance(exc, SessionError) else "ASR_LOCAL_ERROR"
                self.events.put_nowait({"status": "error", "code": code})
        self.thread = threading.Thread(target=work, daemon=False)
        self.thread.start()

    def cancel(self):
        if self.cancel_event is not None:
            self.cancel_event.set()


def main():
    import tkinter as tk
    from tkinter import ttk, filedialog

    root = tk.Tk()
    root.title("Ultron Voice — ASR local (laboratório)")
    root.geometry("720x460")
    controller = SessionController()
    path = tk.StringVar()
    language = tk.StringVar(value="pt")
    status = tk.StringVar(value="Selecione um WAV PCM16 mono, 16 kHz.")
    partial = tk.StringVar()
    closing = False

    frame = ttk.Frame(root, padding=16)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Ultron Voice | Transcrição local").pack(anchor="w")
    ttk.Label(frame, text="Modo laboratório. Microfone e AEC não disponíveis.").pack(anchor="w")
    row = ttk.Frame(frame)
    row.pack(fill="x", pady=12)
    ttk.Entry(row, textvariable=path, state="readonly").pack(side="left", fill="x", expand=True)
    def browse():
        chosen = filedialog.askopenfilename(filetypes=[("WAV PCM", "*.wav")])
        if chosen:
            path.set(chosen)
    choose = ttk.Button(row, text="Selecionar WAV", command=browse)
    choose.pack(side="left", padx=6)
    controls = ttk.Frame(frame)
    controls.pack(fill="x")
    combo = ttk.Combobox(controls, textvariable=language, values=("pt", "en"), state="readonly", width=5)
    combo.pack(side="left")
    result = tk.Text(frame, height=12, wrap="word", state="disabled")
    def show_text(text):
        result.configure(state="normal")
        result.delete("1.0", "end")
        result.insert("1.0", text)
        result.configure(state="disabled")
    def set_running(running):
        start.configure(state="disabled" if running else "normal")
        stop.configure(state="normal" if running else "disabled")
        choose.configure(state="disabled" if running else "normal")
        combo.configure(state="disabled" if running else "readonly")
    def begin():
        if not path.get():
            status.set("Selecione um arquivo WAV.")
            return
        try:
            controller.start(path.get(), language.get())
        except SessionError:
            status.set("Sessão ocupada.")
            return
        show_text("")
        partial.set("")
        status.set("Processando localmente...")
        set_running(True)
    def cancel():
        controller.cancel()
        status.set("Cancelando...")
        stop.configure(state="disabled")
    start = ttk.Button(controls, text="Transcrever", command=begin)
    start.pack(side="left", padx=8)
    stop = ttk.Button(controls, text="Cancelar", command=cancel, state="disabled")
    stop.pack(side="left")
    ttk.Label(frame, textvariable=status).pack(anchor="w", pady=8)
    ttk.Label(frame, textvariable=partial, wraplength=650).pack(anchor="w")
    result.pack(fill="both", expand=True)
    def poll():
        while True:
            try:
                event = controller.events.get_nowait()
            except queue.Empty:
                break
            if event.get("status") == "completed":
                if controller.cancel_event.is_set():
                    show_text("")
                    status.set("Sessão cancelada.")
                else:
                    show_text(event["text"])
                    status.set("Transcrição concluída. Revisão humana necessária.")
                partial.set("")
            elif event.get("status") == "error":
                show_text("")
                partial.set("")
                status.set("Sessão encerrada: " + event["code"])
            elif event.get("type") in ("partial", "final") and not controller.cancel_event.is_set():
                partial.set("Provisório: " + event["text"])
        if closing and not controller.active:
            root.destroy()
            return
        if not controller.active and not closing:
            set_running(False)
        root.after(50, poll)
    def close():
        nonlocal closing
        closing = True
        controller.cancel()
        set_running(True)
        status.set("Encerrando sessão...")
    root.protocol("WM_DELETE_WINDOW", close)
    root.after(50, poll)
    root.mainloop()


if __name__ == "__main__":
    main()
