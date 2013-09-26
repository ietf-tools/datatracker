
# on development host.
# these will need to be adjusted to the host being deployed to.
set :application, "orlando"
set :user, 'orlando'
set :subdir, ""
set :deploy_to, "/data/#{user}/#{subdir}#{application}"
set :pythonver, "2.6"
set :virtualenv, "/data/pythonenv/IETFDB"
set :use_sudo, false

# this depends upon the source of the code.
# branch is not as meaningful for SVN.
set :scm_user, ENV['LOGNAME']
set :ssh_options, { :forward_agent => true }

# GIT
set :scm, :git
set :branch, 'master'
set :repository,  "git+ssh://#{scm_user}@code.gatineau.credil.org/git/orlando/ietfdb"
set :git_enable_submodules, true

# SVN
#set :scm, :subversion
#set :repository,  "http://svn.tools.ietf.org/svn/tools/ietfdb/branch/ssw/agenda/v4.41"

set :django_environment, "cd #{release_path}"

# host list
role :web, "orlando.gatineau.credil.org"
role :app, "orlando.gatineau.credil.org"

namespace :deploy do

# the untouched "deploy" namespace contains:
# deploy:setup
# deploy:default
#   deploy:update
#     deploy:update_code
#       deploy:finalize_update
#     deploy:symlink
#   deploy:restart
#
#
# update_code does the actual checkout/clone, then calls finalize_update.  So you can override
# finalize_update and still get the checkout and symlink functionality.
#
# setup has to be called separately.

  # this overrides rails specific things.
  task :start do ; end
  task :stop do ; end

  desc "Setup a new django instance"
  task :setup, :roles => [:app,:web] do
    setup_deploy_user_home_dir
    logdir
  end


  desc "Restart the apache server."
  task :restart, :roles => :web, :except => { :no_release => true } do
    # something to restart django.
    run "sudo /usr/sbin/apache2ctl graceful"
  end

  desc "Adjust a newly checked-out release for use."
  task :finalize_update, :roles => [:app,:web,:db] do
    copy_settings
    #compilemessages
    run "env"
  end

  desc "Copies settings_local.py to the new release."
  task :copy_settings, :roles => [:app,:web] do
    db_config = "/data/#{user}/settings_local.py"
    run "cp #{db_config} #{release_path}/ietf/settings_local.py"
    releasenum=File.basename(release_path)
    run "echo 'RELEASENUM = \'#{releasenum}\'' >#{release_path}/ietf/releasenum.py"
  end

  desc "./manage.py compilemessages in the new release."
  task :compilemessages, :roles => [:app,:web] do
    #run "chmod 2775 #{release_path}/locale/en/LC_MESSAGES"
    #run "chmod 2775 #{release_path}/locale/fr/LC_MESSAGES"
    run "#{django_environment} && ./manage compilemessages -v 2"
  end

  desc "./manage.py syncdb --noinit in the new release."
  task :syncdb, :roles => [:app,:web] do
    run "#{django_environment} && ./manage syncdb --noinput"
  end

  desc "./manage.py migrate in the new release."
  task :migrate, :roles => [:app,:web] do
    run "#{django_environment} && ./manage migrate"
  end

  desc "Creates the (shared) log directory."
  task :logdir, :roles => [:app,:web] do
    run "mkdir -p #{deploy_to}/log"
  end

  desc "Set up deploy user\'s directory."
  task :setup_deploy_user_home_dir, :roles => [:app,:web] do
    run "mkdir -p #{deploy_to}"
    run "mkdir -p #{deploy_to}/releases"
    logdir
    run "echo 'Do not forget to copy the settings_local.py to the deploy home dir.'"
  end

end

