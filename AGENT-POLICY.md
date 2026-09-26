# Reviewer agent policy

- Bash(rm *): file deletion has irreversible blast radius and remains an explicit repository-owner decision.
- Bash(git push *): publishing commits changes shared remote state and requires direct repository-owner approval.
- Bash(docker *): container commands can alter persistent volumes and running services beyond a read-only review.
