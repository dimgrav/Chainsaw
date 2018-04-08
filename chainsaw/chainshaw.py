import hashlib
import json
import requests

from textwrap import dedent
from time import time
from uuid import uuid4
from urllib.parse import urlparse

from flask import Flask, jsonify, request

'''
Block chain management class
'''
class Chainshaw(object):
    def __init__(self):
        self.current_transactions = []
        self.chain = []
        # The first block of the chain
        self.new_block(previous_hash=1, proof=100)
        # Instantiate node set
        self.nodes = set()

    def new_block(self, proof, previous_hash):
        # New block to be added to chain
        block = {
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'transactions': self.current_transactions,
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.chain[-1]),
        }
        # Reset current transaction list
        self.current_transactions = []
        # Add block to the chain
        self.chain.append(block)
        return block

    def new_transaction(self, sender, recipient, amount):
        # New transaction to be added to transactions
        self.current_transactions.append({
            'sender': sender,
            'recipient': recipient,
            'amount': amount,
        })

        return self.last_block['index'] + 1

    @staticmethod
    def hash(block):
        # Create and hash the block string
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    @property
    def last_block(self):
        # Get last block
        return self.chain[-1]

    def proof_of_work(self, last_proof):
        '''
        PoW Algorithm:
        Return proof y where hash(xy) starts with four zeroes and x is the previous proof
        '''
        proof = 0
        while self.valid_proof(last_proof, proof) is False:
            proof += 1
        return proof

    @staticmethod
    def valid_proof(last_proof, proof):
        # Validate proof of work
        guess = f'{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:4] == "0000"

    def register_node(self, address):
        parsed_url = urlparse(address)
        self.nodes.add(parsed_url.netloc)

    def valid_chain(self, chain):
        last_block = chain[0]
        current_index = 1
        while current_index < len(chain):
            block = chain[current_index]
            print(f'{last_block}')
            print(f'{block}')
            print("\n-----------\n")
            # Validate block hash
            if block['previous_hash'] != self.hash(last_block):
                return False
            # Validate proof of work
            if not self.valid_proof(last_block['proof'], block['proof']):
                return False
            # Update block and corresponding index
            last_block = block
            current_index += 1
        
        return True

    def resolve_conflicts(self):
        '''
        (Simple) Consensus algorithm:
        Sets the longest existing chain as the valid one in the network
        '''
        neighbours = self.nodes
        new_chain = None
        max_length = len(self.chain)

        for node in neighbours:
            # Get all network chains
            response = requests.get(f'http://{node}/chain')

            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain
        
        if new_chain:
            self.chain = new_chain
            return True

        return False


'''
API Resources
'''
# Start Flask app
app = Flask(__name__)
# Generate unique node id
node_identifier = str(uuid4()).replace('-', '')
# Create block chain class instance
blockchain = Chainshaw()

# API routes
@app.route('/mine', methods=['GET'])
def mine():
    last_block = blockchain.last_block
    last_proof = last_block['proof']
    proof = blockchain.proof_of_work(last_proof)

    blockchain.new_transaction(
        sender="0",
        recipient=node_identifier,
        amount=1,
    )

    previous_hash = blockchain.hash(last_block)
    block = blockchain.new_block(proof, previous_hash)

    response = {
        'message': "Created new block.",
        'index': block['index'],
        'transactions': block['transactions'],
        'proof': block['proof'],
        'previous_hash': block['previous_hash'],
    }
    return jsonify(response), 200

@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.get_json()
    required = ['sender', 'recipient', 'amount']

    # POST data integrity validation check
    if not all(k in values for k in required):
        return 'Error: missing values', 400
    # Create transaction based on the valid POST data
    index = blockchain.new_transaction(values['sender'], values['recipient'], values['amount'])

    response = {'message': f'Transaction will be appended to Block{index}'}
    return jsonify(response), 201

@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
    }
    return jsonify(response), 200

@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()
    nodes = values.get('nodes')

    # Network node set validation
    if nodes is None:
        return 'Error: invalid node set', 400
    
    for node in nodes:
        blockchain.register_node(node)

    response = {
        'message': 'Nodes added',
        'new_chain': list(blockchain.nodes),
    }
    return jsonify(response), 201

@app.route('/nodes/resolve', methods=['GET'])
def establish_consensus():
    authoritative = blockchain.resolve_conflicts()

    # Check
    if authoritative:
        response = {
            'message': 'Replaced block chain',
            'new_chain': blockchain.chain
        }
    else:
        response = {
            'message': 'Block chain is authoritative',
            'chain': blockchain.chain
        }
    return jsonify(response), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)