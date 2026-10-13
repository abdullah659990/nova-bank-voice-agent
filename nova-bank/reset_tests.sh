#!/bin/bash
# Undo everything the tool tests changed
docker exec n8n-postgres-1 psql -U bank -d novabank -c "
DELETE FROM transactions WHERE txn_id LIKE 'TR%';
DELETE FROM card_replacements;
UPDATE cards SET status = 'active' WHERE card_id IN (SELECT card_id FROM card_actions WHERE action = 'block');
DELETE FROM card_actions;
UPDATE transactions SET status = 'posted' WHERE status = 'disputed';
DELETE FROM disputes;
DELETE FROM tickets WHERE source = 'voice_agent';
DELETE FROM verification_attempts;
"
echo "Test changes undone."
