db = db.getSiblingDB('afroo_v4');
db.createCollection('users');
db.createCollection('wallets');
db.createCollection('exchanges');
db.createCollection('tickets');
db.createCollection('partners');
db.createCollection('exchangers');
db.createCollection('blockchain_transactions');
db.createCollection('audit_logs');
db.createCollection('counters');

db.counters.insertOne({
  _id: 'ticket_number',
  sequence_value: 1000
});

print('Afroo database initialized successfully');
