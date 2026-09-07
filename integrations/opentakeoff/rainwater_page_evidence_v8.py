from __future__ import annotations

import re
from typing import Any

import pipe_reconcile_v8 as diameter

DIA = diameter.DIAMETER_RX
STANDALONE_RL_RX = re.compile(rf"(?P<dia>{DIA})\s*(?<![A-Z])RL(?![A-Z])", re.IGNORECASE)
RFD_RL_RX = re.compile(rf"(?P<dia>{DIA})\s*(?<![A-Z])RFD\s*\+\s*RL(?![A-Z])", re.IGNORECASE)


def _hits(pattern: re.Pattern[str], text: str, role: str) -> list[dict[str, Any]]:
    out=[]
    for m in pattern.finditer(str(text or '')):
        try:
            norm=diameter.normalize_diameter(m.group('dia'))
        except ValueError:
            continue
        out.append({
            'role':role,
            'matched_text':m.group(0),
            'span':[int(m.start()),int(m.end())],
            **norm,
        })
    return out


def corroborated_rl_class(text: str) -> dict[str, Any]:
    """Return one RL diameter only when two independent page labels corroborate it.

    Required evidence on the same drawing page:
    1) at least one explicit `<diameter>RL` label; and
    2) at least one explicit `<same diameter>RFD+RL` label.
    Any conflicting diameter in either role withholds propagation.
    """
    standalone=_hits(STANDALONE_RL_RX,text,'STANDALONE_RL')
    combined=_hits(RFD_RL_RX,text,'RFD_PLUS_RL')
    all_hits=standalone+combined
    standalone_classes={h['diameter_key'] for h in standalone}
    combined_classes={h['diameter_key'] for h in combined}
    all_classes={h['diameter_key'] for h in all_hits}
    if not standalone or not combined:
        return {
            'status':'WITHHELD_RL_CORROBORATION_INCOMPLETE',
            'standalone_rl_classes':sorted(standalone_classes),
            'rfd_plus_rl_classes':sorted(combined_classes),
            'evidence':all_hits,
        }
    if len(all_classes)!=1:
        return {
            'status':'WITHHELD_RL_CORROBORATION_CONFLICT',
            'standalone_rl_classes':sorted(standalone_classes),
            'rfd_plus_rl_classes':sorted(combined_classes),
            'evidence':all_hits,
        }
    key=next(iter(all_classes))
    representative=next(h for h in all_hits if h['diameter_key']==key)
    return {
        'status':'CORROBORATED_RL_DIAMETER',
        'system':'RL',
        'diameter_key':key,
        'dn':representative.get('dn'),
        'diameter_mm':representative.get('diameter_mm'),
        'diameter_in':representative.get('diameter_in'),
        'standalone_rl_count':len(standalone),
        'rfd_plus_rl_count':len(combined),
        'evidence':all_hits,
        'publication_role':'DIAMETER_EVIDENCE_ONLY_NO_ADDED_LENGTH',
    }


def apply_to_assignments(assignments: list[dict[str, Any]], evidence: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows=[dict(r) for r in assignments]
    if evidence.get('status')!='CORROBORATED_RL_DIAMETER':
        return rows,{
            'status':evidence.get('status'),
            'seeded_segment_count':0,
            'seeded_length_pt':0.0,
        }
    cls={
        'system':'RL',
        'diameter_key':evidence['diameter_key'],
        'dn':evidence.get('dn'),
        'diameter_mm':evidence.get('diameter_mm'),
        'diameter_in':evidence.get('diameter_in'),
    }
    seeded=0; seeded_length=0.0
    for row in rows:
        if str(row.get('layer') or '').upper()!='RL':
            continue
        if not str(row.get('status') or '').startswith('WITHHELD'):
            continue
        if row.get('classes'):
            continue
        row['classes']=[cls]
        row['status']='PAGE_CORROBORATED_RL_DIAMETER'
        row['diameter_evidence_role']='PAGE_STANDALONE_RL_PLUS_RFD_RL'
        seeded+=1; seeded_length+=float(row.get('length_pt',0.0))
    return rows,{
        'status':'APPLIED_CORROBORATED_RL_DIAMETER' if seeded else 'CORROBORATED_RL_NO_WITHHELD_SEGMENTS',
        'diameter_key':evidence['diameter_key'],
        'seeded_segment_count':seeded,
        'seeded_length_pt':round(seeded_length,3),
    }
