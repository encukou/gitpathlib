import pygit2

def make_repo(path, description, bare=True):
    repo = pygit2.init_repository(path, bare=bare)
    parents = []
    for revision in description:
        tree = make_tree(repo, revision['tree'])
        signature = pygit2.Signature('Test', 'test@noreply.invalid')
        commit = repo.create_commit(
            'refs/heads/master',
            signature, signature,
            'Initial commit',
            tree,
            parents,
        )
        parents = [commit]

def make_tree(repo, description):
    builder = repo.TreeBuilder()
    for name, value in description.items():
        if isinstance(value, str):
            item = repo.create_blob(value)
            attr = pygit2.GIT_FILEMODE_BLOB
        else:
            item = make_tree(repo, value)
            attr = pygit2.GIT_FILEMODE_TREE
        builder.insert(name, item, attr)
    return builder.write()
