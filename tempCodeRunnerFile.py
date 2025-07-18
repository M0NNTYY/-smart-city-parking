def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect("/login")