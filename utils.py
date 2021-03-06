import numpy as np
from keras.utils import to_categorical
from keras.losses import categorical_crossentropy
import keras.backend as K
import tensorflow as tf
import math
from tqdm import tqdm
from sklearn.utils import shuffle
from keras.datasets import mnist

def generate_test_data():
    X = np.random.rand(100,20)
    Y = np.array([0]*10 + [1]*10 +[2]*10 + [3]*10 + [4]*10 + [5]*10 + [6]*10 + [7]*10 + [8]*10 + [9]*10)
    return X,Y

def load_vowels(path='vowels'):
    # enumerating labels, original values can be retrieved by indexing the 'labels' array
    if path == "vowels":
        labels = ['a', 'aa', 'i', 'ee',  'u', 'oo', 'ae', 'ai', 'o', 'au', 'an', 'ah']
    num_labels = []
    for num, val in enumerate(labels):
      num_labels.append(num)
    folders = [i+1 for i in num_labels] # adding ones, since folders are arranged from 1-12
    X = []
    y = []
    for f in folders:
      abs_path = os.path.join(path, str(f))
      for img in os.listdir(abs_path):
        X.append(cv2.imread(os.path.join(abs_path, img), cv2.IMREAD_GRAYSCALE))
        y.append(f - 1) # converting fodler value to original label val
    X = np.array(X)
    y = np.array(y)

    # normalizing the input data modify if necessary
    X = tf.keras.utils.normalize(X, axis = 1).reshape(X.shape[0],-1)
    y = to_categorical(y)
    return X, y


def divide_dataset_into_tasks(X,Y,T):
    Y_categorical = to_categorical(Y)
    dropped = Y_categorical.shape[1] % T
    classes = Y_categorical.shape[1] - dropped
    if dropped is not 0:
        Y_categorical = Y_categorical[:,0:-1*dropped]
    per_task = classes/T
    tasks = []
    labels = []
    i=0
    while i<int(classes):
        X_t = None
        Y_t = None
        mask = None
        for j in range(0,int(per_task)):
            mask = (Y == i+j)
            if X_t is None:
                X_t = X[mask]
                Y_t = Y_categorical[mask]
            else:
                X_t=np.concatenate([X_t, X[mask]])
                Y_t=np.concatenate([Y_t, Y_categorical[mask]])
        
        tasks.append(X_t)
        labels.append(Y_t)
        i+=per_task
    return tasks, labels

def split_train_test(tasks,labels,fraction=0.2):
    new_tasks = []
    new_labels = []
    test_tasks = []
    test_labels = []
    for i in range(len(tasks)):
        last_n=int(tasks[i].shape[0]*fraction)
        new_tasks.append(tasks[i][last_n:])
        new_labels.append(labels[i][last_n:])
        test_tasks.append(tasks[i][0:last_n])
        test_labels.append(labels[i][0:last_n])        
    return new_tasks,new_labels,test_tasks,test_labels


def get_permute_mnist_tasks(task_no,samples_per_task=60000):
    (x_train, y_train), (x_test, y_test) = mnist.load_data()
    x_train, y_train = shuffle(x_train,y_train)
    x_train=x_train.reshape(60000,784)/255.0
    y_train=to_categorical(y_train)
    x_train=x_train[0:samples_per_task]
    y_train=y_train[0:samples_per_task]
    tasks = []
    #tasks.append(x_train)
    labels = []
    #labels.append(y_train)
    def make_y(row, task):
        emp = np.zeros(10*task_no)
        emp[task*10:task*10+10] = row
        return emp
    for i in tqdm(range(task_no)):
        mask = np.random.permutation(784)
        tasks.append(np.apply_along_axis(lambda x: x[mask],1,x_train))
        y_train_expanded = np.apply_along_axis(make_y,1,y_train,i)
        labels.append(y_train_expanded)
    return tasks, labels

    
    
def slope_reg(X,Y,intercept):
    #X*w+b=Y
    #loss=(y-(Xw+b)) * (y-(Xw+b))=
    #y*y - 2*(Xw+b)*y + (Xw+b)*(Xw+b)=
    #y*y - 2*(Xw*y+b*y) + (Xw+b)*(Xw+b)=
    #y*y - 2*Xw*y - 2*b*y + Xw*Xw + 2*Xw*b + b*b
    
    #dloss/dw = 0
    #-2*X*y + 2*X*X*w + 2*X*b = 0
    #2*X*X*w + 2*X*b = 2*X*y
    #X*X*w + X*b = X*y
    #w=(X*y-X*b)/(X*X)
    
    w = (np.dot(X,Y)-np.dot(X,np.ones(X.shape[0])*intercept))/np.dot(X,X)
    return w
    

'''
The rate_matrix method takes in the accuracy matrix and constructs a linear
regression model that treats the row-column combinations as X and Y coordinates
that designate regions on a plane and treats the element size as the number
of points in a given region. The regression line's intercept is fixed
at the top left corner of the matrix. The slope is solved for using a 
normal equation. See above.
'''    
def rate_matrix(m,epsilon=0.01):
    m = np.tril(m)
    X = []
    for i in range(m.shape[0]):
        for j in range(m.shape[0]):
            for k in range(int(m[i,j]/epsilon)):
                X.append([j,(m.shape[0]-i-1)])
    X = np.array(X,dtype=np.float64)
    return slope_reg(X[:,0],X[:,1],m.shape[0]-1)
    
    

def estimate_fisher_diagonal(model, X, Y=None, fisher_n=0, len_weights=None, return_gradients=False, true_estimate=True, nonzero_gradient_mean=True, xs=None):
    if xs==None:
        xs=model.trainable_weights
    if len_weights is None:
        len_weights = len(K.batch_get_value(model.trainable_weights))
    fisher_estimates = [np.zeros_like(w) for w in K.batch_get_value(model.trainable_weights)[0:len_weights]]
    if fisher_n is 0 or fisher_n>X.shape[0]:
        fisher_n = X.shape[0]
    true_length = len(X)
    X=X[0:fisher_n]
    gradients = []
    sess=K.get_session()    
    if Y is None:
        X = np.random.permutation(X)
        #note for future: turns a model output vector (e.g. [0.3, 0.4, 0.2, 0.1]) into a one-hot (e.g. [0,1,0,0]) by keeping making a max-only copy, making a boolean vector by checking element equality with the elements of the original, and drawing from 0s where false and 1s when true.
        label_tensor = tf.where(tf.equal(tf.reduce_max(model.output,1,keepdims=True),model.output),tf.constant(1,shape=(1,model.output.shape[1])),tf.constant(0,shape=(1,model.output.shape[1])))
        grads_tensor = K.gradients(categorical_crossentropy(label_tensor,model.output),xs)        
    else:
        Y=Y[0:fisher_n]        
        X,Y = shuffle(X,Y)        
        label=Y
        y_placeholder = K.placeholder(dtype='float32', shape=label[0].shape)
        grads_tensor = K.gradients(categorical_crossentropy(y_placeholder,model.output),xs)        
    for i in tqdm(range(fisher_n), desc='Calculating gradients'):
        feed_dict={model.input:np.array([X[i]])}
        if Y is not None:
            feed_dict[y_placeholder]=Y[i]
        gradient = sess.run(grads_tensor, feed_dict=feed_dict)
        gradients.append(gradient)
    if nonzero_gradient_mean:
        gradient_means=[]
        for j in tqdm(range(len_weights), desc='Calculating gradient means'):
            grad_sum = 0
            for i in range(fisher_n):
                grad_sum+=gradients[i][j]
            grad_sum/=fisher_n
            gradient_means.append(grad_sum)
    else:
        gradient_means=[]
        for j in range(len_weights):
            gradient_means.append(0)
    for i in tqdm(range(fisher_n), desc='Estimating FIM diagonal'):
        for j in range(len_weights):
            fisher_estimates[j]+=(gradients[i][j]-gradient_means[j])**2/fisher_n
    fisher_estimates = [(true_length if true_estimate else 1)*x for x in fisher_estimates]
    if return_gradients:
        return fisher_estimates, gradients
    return fisher_estimates
