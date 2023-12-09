from datetime import datetime
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from social_media import db, login_manager, app
from flask_login import UserMixin
import numpy as np
import tensorflow as tf
import json


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    image_file = db.Column(db.String(20), nullable=False, default='default.jpg')
    password = db.Column(db.String(60), nullable=False)
    posts = db.relationship('Post', backref='author', lazy=True)
    history = db.Column(db.JSON)
    future = db.Column(db.String(300))

    def get_reset_token(self, expires_sec=1800):
        s = Serializer(app.config['SECRET_KEY'], expires_sec)
        return s.dumps({'user_id': self.id}).decode('utf-8')

    @staticmethod
    def verify_reset_token(token):
        s = Serializer(app.config['SECRET_KEY'])
        try:
            user_id = s.loads(token)['user_id']
        except:
            return None
        return User.query.get(user_id)
    
    def predict_history(self):
        mapping = {'entertainment': 1, 'finance': 2, 'foodanddrink': 3, 'games': 4, 'health': 5, 'kids': 6, 
                   'lifestyle': 7, 'movies': 8, 'news': 9, 'sports': 10, 'tv': 11, 'auto': 12} 
        # Load the saved model
        model = tf.keras.models.load_model('C:\\Users\\boudh\\Desktop\\Social media site\\website\\social_media\\static\\LTSM_model.h5')
        input_list = [[]]
        my_hist = self.history
        if my_hist is not None:
            my_hist = json.loads(my_hist)
            if len(my_hist["prediction"]) != 0:
                for x in my_hist["prediction"]:
                    input_list[0].append(x[0])
            
                new_input_list = [[mapping.get(item, item) for item in sublist] for sublist in input_list]
            
                int_input_list = [[]]
                for sub_list in new_input_list:
                    for element in sub_list:
                        if isinstance(element, int):
                            int_input_list[0].append(element)
                        elif isinstance(element, str) and element.isdigit():
                            int_input_list[0].append(int(element))
            
                int_input_list = np.array(int_input_list)
                padded_list = np.pad(int_input_list, ((0, 0), (0, 75 - int_input_list.shape[1])), 'constant')
                prediction = model.predict(padded_list)
                sorted_indices = np.argsort(prediction[0])[::-1]
                future = ""
                for i in sorted_indices[:3]:
                    future = future + str(str([k for k, v in mapping.items() if v == i][0])+" ("+str(str(round(prediction[0][i]*100, 2))+"%),"))

                print(future)
                self.future = future
                my_hist['prediction'] = []
                history_string = json.dumps(my_hist)
                self.history = history_string
                db.session.commit()

                return "succes"
            
        return "No predictions available for this user"
    
    def prediction_empty(self):

        my_hist = self.history
        if my_hist is not None :
            my_hist = json.loads(my_hist)
            if len(my_hist["prediction"]) == 0:
                return False
            else:
                return True
        else :
            return False
    
    def intrest_empty(self):
        my_future = self.future
        if my_future is not None :
           return True
        else :
            return False

    def __repr__(self):
        return f"User('{self.username}', '{self.email}', '{self.image_file}')"


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(20), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        return f"Post('{self.title}', '{self.date_posted}', '{self.category}')"


"""
from social_media import db, app
with app.app_context(): db.create_all()
"""