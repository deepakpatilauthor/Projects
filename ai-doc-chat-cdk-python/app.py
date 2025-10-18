
#!/usr/bin/env python3
import aws_cdk as cdk
from cdk.stacks.ai_doc_chat_stack import AIDocChatStack

app = cdk.App()
AIDocChatStack(app, "AIDocChatStack")

app.synth()
