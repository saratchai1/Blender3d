#!/usr/bin/env python3
from __future__ import annotations

import strict_pipe_tags_v8 as strict


def classes(text: str):
    return [(r['system'], r['diameter_key']) for r in strict.extract_pipe_tag_classes(text)]


def main() -> None:
    assert classes('PASS Ø3/4" BY PASS') == [], classes('PASS Ø3/4" BY PASS')
    assert classes('BYPASS Ø1"') == [], classes('BYPASS Ø1"')
    assert classes('SWING Ø2"') == [], classes('SWING Ø2"')
    assert classes('Ø2" W') == [('W','DN50')]
    assert classes('W Ø2"') == [('W','DN50')]
    assert classes('Ø4"SW') == [('SW','DN100')]
    assert classes('CW DN25') == [('CW','DN25')]
    assert classes('DN50 V') == [('V','DN50')]
    assert classes('RL Ø21/2"') == [('RL','DN65')]
    print('STRICT_PIPE_TAGS_V8_TEST_PASS', {'embedded_word_false_positive':'rejected','valid_forms':'preserved'})


if __name__ == '__main__':
    main()
