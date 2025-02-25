from datetime import date
from flask import Flask, abort, render_template, redirect, url_for, flash, request
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user, login_required
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text, ForeignKey
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
# Import your forms from the forms.py
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
import os
import psycopg2




app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("CONFIG_FLASK")
ckeditor = CKEditor(app)
app.config['CKEDITOR_SERVE_LOCAL'] = True
Bootstrap5(app)

gravatar = Gravatar(app, size=20,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)

login_manager = LoginManager()

login_manager.init_app(app)
app.config['SECRET_KEY'] = os.environ.get("CONFIG_SEC")



class Base(DeclarativeBase):
    pass


app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DB_URL")
db = SQLAlchemy(model_class=Base)
db.init_app(app)

@login_manager.user_loader
def load_user(user_id: str):
    return User.query.get(int(user_id))

class User(db.Model, UserMixin):
    __tablename__ = "user_table"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True, nullable=False)
    password: Mapped[str] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(nullable=False)
    children_posts = relationship("BlogPost", back_populates="parent_author")
    children_comment = relationship("Comment", back_populates="parent_author")

# CONFIGURE TABLES
class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    author_id: Mapped[int] = mapped_column(db.ForeignKey("user_table.id"))
    parent_author = relationship("User", back_populates="children_posts")

    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    img_url: Mapped[str] = mapped_column(String(250), nullable=False)
    children_comment = relationship("Comment", back_populates="post_comment_rel")


class Comment(db.Model):
    __tablename__ = "comment_table"
    id: Mapped[int] = mapped_column(primary_key=True)

    author_id: Mapped[int] = mapped_column(db.ForeignKey("user_table.id"))
    parent_author = relationship("User", back_populates="children_comment")

    post_id: Mapped[int] = mapped_column(db.ForeignKey('blog_posts.id'))
    post_comment_rel = relationship("BlogPost", back_populates="children_comment")

    text: Mapped[str] = mapped_column(Text, nullable=False,)


with app.app_context():
    db.create_all()



def only_admin(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if current_user.is_anonymous:
            return abort(406)
        elif current_user.id != 1:
            return abort(403)
        else:
            return func(*args, **kwargs)
    return wrapper



@app.route('/register', methods=["POST", "GET"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        user_exist = db.session.execute(db.select(User).filter_by(email=form.email.data)).scalar()
        if user_exist:
            flash("This email is already exist, please log in!")
            return redirect(url_for('login'))
        else:

            user = User()
            user.email = form.email.data
            user.name = form.name.data
            user.password = generate_password_hash(
                form.password.data, method="pbkdf2:sha256", salt_length=8)

            db.session.add(user)
            db.session.commit()

            login_user(user)

            return redirect(url_for('get_all_posts', current_user=current_user.is_authenticated))
    return render_template("register.html", form=form, current_user=current_user)



@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email_entered = form.email.data
        pw_entered = form.password.data

        is_user = db.session.execute(db.select(User).where(User.email == email_entered)).scalar()

        if not is_user:
            flash("This email is not exist")
            return redirect(url_for('login'))
        elif not check_password_hash(pwhash=is_user.password, password=pw_entered):
            flash("The password is wrong.")
            return redirect(url_for('login'))
        else:
            login_user(is_user)
            return redirect(url_for('get_all_posts', current_user=current_user.is_authenticated))

    return render_template("login.html", form=form, current_user=current_user)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/')
def get_all_posts():
    result = db.session.execute(db.select(BlogPost)).scalars().all()
    return render_template("index.html", all_posts=result, current_user=current_user)



@app.route("/post/<int:post_id>", methods=["POST", "GET"])
def show_post(post_id):
    form = CommentForm()
    requested_post = db.get_or_404(BlogPost, post_id)

    if form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("You need to login or register to comment.")
            return redirect(url_for('login'))
        comment = Comment(
            text=form.comment.data,
            parent_author=current_user,
            post_comment_rel=requested_post
        )


        db.session.add(comment)
        db.session.commit()


    return render_template("post.html", post=requested_post, form=form, current_user=current_user)


@app.route("/new-post", methods=["GET", "POST"])
@only_admin
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            parent_author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form, current_user=current_user)



@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@only_admin
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        parent_author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.parent_author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True, current_user=current_user)


@app.route("/delete/<int:post_id>")
@only_admin
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route("/about")
def about():
    return render_template("about.html", current_user=current_user)


@app.route("/contact")
def contact():
    return render_template("contact.html", current_user=current_user)


if __name__ == "__main__":
    app.run(debug=True, port=5002)





