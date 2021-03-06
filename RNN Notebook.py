# Import TensorFlow >= 1.9 and enable eager execution
import tensorflow as tf

# Note: Once you enable eager execution, it cannot be disabled. 
tf.enable_eager_execution()

import numpy as np
import re
import random
import unidecode
import time
import unicodedata
from __future__ import unicode_literals
import os, re

#####
#  Experiment with these values:
#####
# number of characters to generate
num_generate = 1000

# You can change the start string to experiment
# PS, Whatever you specify here, letter or full string, MUST BE IN YOUR TRAINING FILE
start_string = 'A'

# low temperatures results in more predictable text.
# higher temperatures results in more surprising text
# experiment to find the best setting
temperature = .7

#EPOCHS are loosly the number of times it will run the text through the model
# The more you do this the "smarter" the model gets. Numbers of 1000's or even 
#10's of 1000's are not uncommon - lower numbers make your AI not very smart
EPOCHS = 10

#Keras Utils have a nasty tendancy to "cache" the file for training. Really annoying 
#if you are trying to get real result. This little bit flushes out the cache before it checks:
def purge(dir, pattern):
    for f in os.listdir(dir):
        if re.search(pattern, f):
            os.remove(os.path.join(dir, f))
kpath = "/root/.keras/datasets/"
kpattern = ".txt"
purge(kpath, kpattern)


#this should simplify defining the keras utils path and file
thefile = 'realybadtrainingtext.txt'
thepath = 'https://raw.githubusercontent.com/ChrisHarrold/ML-AI-Code/master/realybadtrainingtext.txt'

path_to_file = tf.keras.utils.get_file(thefile, thepath)
#this isn't needed anymore, but the file ALWAYS comes from the local /root/.keras/datafiles dir
#print (path_to_file)

#Fun with unicode! This block strips out unicode information so you don't have blow-ups
#on non-unicode. It flat DROPS the text, so if you want it, you need a better method
trainingtext = open(path_to_file).read()
trainingtext = ''.join(i for i in trainingtext if ord(i)<128)
text = unidecode.unidecode(trainingtext)
# length of text is the number of characters in it
print ("The text is this many characters:")
print (len(text))
#not sure the purge is working? Uncomment to see what you are getting!
#print (text)

# unique contains all the unique characters in the file
unique = sorted(set(text))

# creating a mapping from unique characters to indices
char2idx = {u:i for i, u in enumerate(unique)}
idx2char = {i:u for i, u in enumerate(unique)}

# setting the maximum length sentence we want for a single input in characters
max_length = 100

# length of the vocabulary in chars
vocab_size = len(unique)

# the embedding dimension 
embedding_dim = 256

# number of RNN (here GRU) units
units = 1024

# batch size 
BATCH_SIZE = 64

# buffer size to shuffle our dataset
BUFFER_SIZE = 10000

# empty string to store our results
text_generated = ''
#intitialize our training corpus arrays
input_text  = []
target_text = []

for f in range(0, len(text)-max_length, max_length):
    inps = text[f:f+max_length]
    targ = text[f+1:f+1+max_length]

    input_text.append([char2idx[i] for i in inps])
    target_text.append([char2idx[t] for t in targ])
    
print (np.array(input_text).shape)
print (np.array(target_text).shape)

dataset = tf.data.Dataset.from_tensor_slices((input_text, target_text)).shuffle(BUFFER_SIZE)
dataset = dataset.apply(tf.contrib.data.batch_and_drop_remainder(BATCH_SIZE))


class Model(tf.keras.Model):
  def __init__(self, vocab_size, embedding_dim, units, batch_size):
    super(Model, self).__init__()
    self.units = units
    self.batch_sz = batch_size

    self.embedding = tf.keras.layers.Embedding(vocab_size, embedding_dim)

    #Check for GPU and initialize a GPU-based model or not
    if tf.test.is_gpu_available():
      self.gru = tf.keras.layers.CuDNNGRU(self.units, 
                                          return_sequences=True, 
                                          return_state=True, 
                                          recurrent_initializer='glorot_uniform')
    else:
      self.gru = tf.keras.layers.GRU(self.units, 
                                     return_sequences=True, 
                                     return_state=True, 
                                     recurrent_activation='sigmoid', 
                                     recurrent_initializer='glorot_uniform')

    self.fc = tf.keras.layers.Dense(vocab_size)
        
  def call(self, x, hidden):
    x = self.embedding(x)

    # output shape == (batch_size, max_length, hidden_size) 
    # states shape == (batch_size, hidden_size)

    # states variable to preserve the state of the model
    # this will be used to pass at every step to the model while training
    output, states = self.gru(x, initial_state=hidden)


    # reshaping the output so that we can pass it to the Dense layer
    # after reshaping the shape is (batch_size * max_length, hidden_size)
    output = tf.reshape(output, (-1, output.shape[2]))

    # The dense layer will output predictions for every time_steps(max_length)
    # output shape after the dense layer == (max_length * batch_size, vocab_size)
    x = self.fc(output)

    return x, states

model = Model(vocab_size, embedding_dim, units, BATCH_SIZE)

optimizer = tf.train.AdamOptimizer()

# using sparse_softmax_cross_entropy so that we don't have to create one-hot vectors
def loss_function(real, preds):
    return tf.losses.sparse_softmax_cross_entropy(labels=real, logits=preds)

# Training step

for epoch in range(EPOCHS):
    start = time.time()
    
    # initializing the hidden state at the start of every epoch
    hidden = model.reset_states()
    
    for (batch, (inp, target)) in enumerate(dataset):
          with tf.GradientTape() as tape:
              # feeding the hidden state back into the model
              # This is the interesting step
              predictions, hidden = model(inp, hidden)
              
              # reshaping the target because that's how the 
              # loss function expects it
              target = tf.reshape(target, (-1,))
              loss = loss_function(target, predictions)
              
          grads = tape.gradient(loss, model.variables)
          optimizer.apply_gradients(zip(grads, model.variables), global_step=tf.train.get_or_create_global_step())

          if batch % 100 == 0:
              print ('Epoch {} Batch {} Loss {:.4f}'.format(epoch+1,
                                                            batch,
                                                            loss))

    #for some unknown reason this throws errors about the 'loss' variable
    #being undefined with the crappy training file. Commented out since it is just
    # a counter and replaced with a simpler one that won't error
    #print ('Epoch {} Loss {:.4f}'.format(epoch+1, loss))
    print ('Epoch took {} seconds\n'.format(time.time() - start))
    
# Evaluation step(generating text using the model learned)

# converting our start string to numbers(vectorizing!) 
input_eval = [char2idx[s] for s in start_string]
input_eval = tf.expand_dims(input_eval, 0)

# hidden state shape == (batch_size, number of rnn units); here batch size == 1
hidden = [tf.zeros((1, units))]
for i in range(num_generate):
    predictions, hidden = model(input_eval, hidden)

    # using a multinomial distribution to predict the word returned by the model
    predictions = predictions / temperature
    predicted_id = tf.multinomial(tf.exp(predictions), num_samples=1)[0][0].numpy()
    
    # We pass the predicted word as the next input to the model
    # along with the previous hidden state
    input_eval = tf.expand_dims([predicted_id], 0)
    
    text_generated += idx2char[predicted_id]

print (start_string + text_generated)