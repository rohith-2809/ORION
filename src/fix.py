
content = open('core/orchestrator.py', 'r').read()

replacements = {
    'import document_engine': 'from skills import document_engine',
    'from document_engine import': 'from skills.document_engine import',
    'from memory import': 'from core.memory import',
    'import memory': 'from core import memory',
    'from brain import': 'from core.brain import',
    'from intent_classifier import': 'from core.intent_classifier import',
    'from file_tools import': 'from skills.file_tools import',
    'from action_ledger import': 'from security.action_ledger import',
    'from reflection import': 'from core.reflection import',
    'from policy import': 'from security.policy import',
    'from rag_memory import': 'from core.rag_memory import',
    'from planner import': 'from core.planner import',
    'from executor import': 'from core.executor import',
    'from tts import': 'from voice.tts import',
    'from conversation_policy import': 'from security.conversation_policy import',
    'from emergency_policy import': 'from security.emergency_policy import',
    'from orion_defense_kernel import': 'from security.orion_defense_kernel import',
    'from authority_manager import': 'from core.authority_manager import',
    'from document_writer import': 'from skills.document_writer import'
}

for k,v in replacements.items():
    content = content.replace(k, v)

with open('core/orchestrator.py', 'w') as f:
    f.write(content)

print('orchestrator.py imports fixed.')
