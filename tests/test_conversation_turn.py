from ultron_voice.conversation_turn import TurnController,State

def test_wake_and_silence():
    c=TurnController()
    assert not c.wake("ultronal")
    assert c.wake("Oi Ultron")
    assert c.frame(speech=True,duration_ms=100)=="CONTINUE"
    assert c.frame(speech=False,duration_ms=800)=="END_TURN"
    assert c.begin_response(c.generation)
    assert c.finish_response(c.generation)

def test_barge_in_ignores_echo_and_invalidates_old_response():
    c=TurnController();c.wake("ultron")
    c.frame(speech=True,duration_ms=100)
    c.frame(speech=False,duration_ms=800)
    g=c.generation;c.begin_response(g)
    assert c.frame(speech=True,duration_ms=500,echo_free=False)=="CONTINUE"
    assert c.frame(speech=True,duration_ms=300,echo_free=True)=="INTERRUPT"
    assert not c.finish_response(g) and c.state==State.LISTENING

def test_gameguard_pause_and_reset():
    c=TurnController()
    assert not c.wake("ultron",game_active=True)
    c.wake("ultron")
    assert c.frame(speech=False,duration_ms=100,game_active=True)=="STOP"
    assert c.state==State.PAUSED
    assert not c.reset(game_active=True)
    assert c.reset()
