"""Pure turn controller for future local ASR/TTS streaming. No microphone or network."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import re

class State(str,Enum):
    IDLE="idle"
    LISTENING="listening"
    THINKING="thinking"
    SPEAKING="speaking"
    PAUSED="paused"

@dataclass
class TurnController:
    wake_word:str="ultron"
    silence_ms:int=800
    interrupt_ms:int=300
    state:State=State.IDLE
    generation:int=0
    quiet_ms:int=0
    voiced_ms:int=0

    def wake(self, transcript:str, *, game_active:bool=False)->bool:
        if game_active or self.state!=State.IDLE:
            return False
        if self.wake_word.casefold() not in re.findall(r"\w+",transcript.casefold()):
            return False
        self.generation+=1
        self.state=State.LISTENING
        self.quiet_ms=self.voiced_ms=0
        return True

    def frame(self, *, speech:bool, duration_ms:int, echo_free:bool=False, game_active:bool=False)->str:
        if not 1<=duration_ms<=1000:
            raise ValueError("INVALID_FRAME_DURATION")
        if game_active:
            self.generation+=1
            self.state=State.PAUSED
            return "STOP"
        if self.state==State.LISTENING:
            self.quiet_ms=0 if speech else self.quiet_ms+duration_ms
            if speech: self.voiced_ms+=duration_ms
            if self.quiet_ms>=self.silence_ms and self.voiced_ms:
                self.state=State.THINKING
                return "END_TURN"
            if self.quiet_ms>=self.silence_ms and not self.voiced_ms:
                self.state=State.IDLE
                return "NO_SPEECH"
        elif self.state==State.SPEAKING:
            self.voiced_ms=self.voiced_ms+duration_ms if speech and echo_free else 0
            if self.voiced_ms>=self.interrupt_ms:
                self.generation+=1
                self.state=State.LISTENING
                self.quiet_ms=self.voiced_ms=0
                return "INTERRUPT"
        return "CONTINUE"

    def begin_response(self, generation:int)->bool:
        if self.state!=State.THINKING or generation!=self.generation:
            return False
        self.state=State.SPEAKING
        self.voiced_ms=0
        return True

    def finish_response(self, generation:int)->bool:
        if self.state!=State.SPEAKING or generation!=self.generation:
            return False
        self.state=State.IDLE
        return True

    def reset(self, *, game_active:bool=False)->bool:
        if game_active: return False
        self.generation+=1
        self.state=State.IDLE
        self.quiet_ms=self.voiced_ms=0
        return True
