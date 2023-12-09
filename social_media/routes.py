import os
import secrets
from PIL import Image
from flask import render_template, url_for, flash, redirect, request, abort
from social_media import app, db, bcrypt, mail
from social_media.forms import (RegistrationForm, LoginForm, UpdateAccountForm,
                             PostForm, RequestResetForm, ResetPasswordForm)
from social_media.models import User, Post
from flask_login import login_user, current_user, logout_user, login_required
from flask_mail import Message
import json
from sqlalchemy.orm import joinedload
import datetime
from flask_paginate import Pagination, get_page_parameter

@app.route("/")
@app.route("/home")
def home():
    page = request.args.get('page', 1, type=int)
    posts = Post.query.order_by(Post.date_posted.desc()).paginate(page=page, per_page=5)
    return render_template('home.html', posts=posts)

@app.route('/search', methods=['GET', 'POST'])
def search():
    category= request.form
    category = category.get('q')
    posts_cat = Post.query.filter_by(category=category).all()
    listcat = ['entertainment','finance','foodanddrink','games','health','kids','lifestyle','movies', 'news','sports','tv','auto']
    if category in listcat:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        user = User.query.filter_by(id=current_user.id).first()
        if user.history is None or user.history == "":
            history_dict = {"pages_visited": [], "prediction": []}
        else:
            history_dict = json.loads(user.history)

        history_dict["pages_visited"].append([category, now])
        history_dict["prediction"].append([category, now])
        history_string = json.dumps(history_dict)
        user.history = history_string
        db.session.commit()

    return render_template('search.html', posts=posts_cat)


@app.route("/about")
def about():
    return render_template('about.html', title='About')


@app.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=form.username.data, email=form.email.data, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash('Your account has been created! You are now able to log in', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)


@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            flash('Login Unsuccessful. Please check email and password', 'danger')
    return render_template('login.html', title='Login', form=form)


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('home'))


def save_picture(form_picture):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(app.root_path, 'static/profile_pics', picture_fn)

    output_size = (125, 125)
    i = Image.open(form_picture)
    i.thumbnail(output_size)
    i.save(picture_path)

    return picture_fn


@app.route("/account", methods=['GET', 'POST'])
@login_required
def account():
    user = User.query.get_or_404(current_user.id)
    try:
        history = json.loads(user.history)
        history = history['pages_visited']
    except:
        history = None

    form = UpdateAccountForm()
    if form.validate_on_submit():
        if form.picture.data:
            picture_file = save_picture(form.picture.data)
            current_user.image_file = picture_file
        current_user.username = form.username.data
        current_user.email = form.email.data
        db.session.commit()
        flash('Your account has been updated!', 'success')
        return redirect(url_for('account'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.email.data = current_user.email
    image_file = url_for('static', filename='profile_pics/' + current_user.image_file)
    return render_template('account.html', title='Account',
                           image_file=image_file, form=form, history=history)


@app.route("/post/new", methods=['GET', 'POST'])
@login_required
def new_post():
    form = PostForm()
    if form.validate_on_submit():
        post = Post(title=form.title.data, content=form.content.data, category=form.category.data, author=current_user)
        db.session.add(post)
        db.session.commit()
        flash('Your post has been created!', 'success')
        return redirect(url_for('home'))
    return render_template('create_post.html', title='New Post',form=form, legend='New Post')


@app.route("/post/<int:post_id>")
def post(post_id):
    post = Post.query.get_or_404(post_id)
    return render_template('post.html', title=post.title, post=post)


@app.route("/post/<int:post_id>/update", methods=['GET', 'POST'])
@login_required
def update_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author != current_user:
        abort(403)
    form = PostForm()
    if form.validate_on_submit():
        post.title = form.title.data
        post.content = form.content.data
        post.category = form.category.data
        db.session.commit()
        flash('Your post has been updated!', 'success')
        return redirect(url_for('post', post_id=post.id))
    elif request.method == 'GET':
        form.title.data = post.title
        form.content.data = post.content
        form.category.data = post.category
    return render_template('create_post.html', title='Update Post',
                           form=form, legend='Update Post')


@app.route("/post/<int:post_id>/delete", methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author != current_user:
        abort(403)
    db.session.delete(post)
    db.session.commit()
    flash('Your post has been deleted!', 'success')
    return redirect(url_for('home'))


@app.route("/user/<string:username>")
def user_posts(username):
    page = request.args.get('page', 1, type=int)
    user = User.query.filter_by(username=username).first_or_404()
    posts = Post.query.filter_by(author=user)\
        .order_by(Post.date_posted.desc())\
        .paginate(page=page, per_page=5)
    return render_template('user_posts.html', posts=posts, user=user)


def send_reset_email(user):
    token = user.get_reset_token()
    msg = Message('Password Reset Request',
                  sender='noreply@demo.com',
                  recipients=[user.email])
    msg.body = f'''To reset your password, visit the following link:
{url_for('reset_token', token=token, _external=True)}
If you did not make this request then simply ignore this email and no changes will be made.
'''
mail.send(msg)


@app.route("/reset_password", methods=['GET', 'POST'])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        send_reset_email(user)
        flash('An email has been sent with instructions to reset your password.', 'info')
        return redirect(url_for('login'))
    return render_template('reset_request.html', title='Reset Password', form=form)


@app.route("/reset_password/<token>", methods=['GET', 'POST'])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    user = User.verify_reset_token(token)
    if user is None:
        flash('That is an invalid or expired token', 'warning')
        return redirect(url_for('reset_request'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user.password = hashed_password
        db.session.commit()
        flash('Your password has been updated! You are now able to log in', 'success')
        return redirect(url_for('login'))
    return render_template('reset_token.html', title='Reset Password', form=form)

@app.route("/admin")
@login_required
def admin():
    id = current_user.id
    if id == 1:
        users = User.query.all()
        per_page = 3
        page = request.args.get(get_page_parameter(), type=int, default=1)
        start = (page - 1) * per_page
        end = start + per_page
        users_on_page = users[start:end]
        pagination = Pagination(page=page, total=len(users), per_page=per_page, css_framework='bootstrap4')
        return render_template('admin.html', users=users_on_page, pagination=pagination)
    else:
        flash("Sorry you must be the admin to access the admin page", 'warning')
        return redirect(url_for('home'))

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    user = User.query.options(joinedload(User.posts)).get_or_404(user_id)
    # delete all posts associated with the user
    for post in user.posts:
        db.session.delete(post)
    db.session.delete(user)
    db.session.commit()
    flash('The user has been deleted!', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/user_posts2/<int:user_id>')
@login_required
def user_posts2(user_id):
    page = request.args.get(get_page_parameter(), type=int, default=1)
    per_page = 7
    user = User.query.get_or_404(user_id)
    posts = Post.query.options(joinedload(Post.author)).filter_by(user_id=user.id).order_by(Post.date_posted.desc())
    pagination = Pagination(page=page, total=posts.count(), per_page=per_page, css_framework='bootstrap4')
    posts_on_page = posts.paginate(page=page, per_page=per_page)
    return render_template('user_posts2.html', user=user, pagination=pagination, posts=posts_on_page)

@login_required
@app.route('/user_posts2/<int:post_id>/delete', methods=['POST'])
def delete_post2(post_id):
    post = Post.query.options(joinedload(Post.author)).get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()
    flash('Your post has been deleted!', 'success')
    return redirect(url_for('user_posts2', user_id=post.author.id))

@app.route('/admin/user_history/<int:user_id>')
@login_required
def user_history(user_id):
    user = User.query.get_or_404(user_id)
    try:
        history = json.loads(user.history)
        history = history['pages_visited']
    except:
        history = None

    return render_template('user_history.html', history=history, user=user)

@app.route('/display_user/<int:user_id>')
def display_user(user_id):
    user = User.query.get_or_404(user_id)
    user.predict_history()
    return redirect(url_for('admin'))